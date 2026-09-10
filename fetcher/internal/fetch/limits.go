package fetch

import (
	"context"
	"sync"

	"golang.org/x/time/rate"
)

type Limits struct {
	perHost   int
	perIP     int
	hostSem   sync.Map
	ipSem     sync.Map
	global    *rate.Limiter
}

func NewLimits(perHost, perIP int, globalRPS float64) *Limits {
	if perHost < 1 {
		perHost = 1
	}
	if perIP < 1 {
		perIP = 4
	}
	burst := int(globalRPS * 2)
	if burst < 1 {
		burst = 1
	}
	var global *rate.Limiter
	if globalRPS > 0 {
		global = rate.NewLimiter(rate.Limit(globalRPS), burst)
	}
	return &Limits{perHost: perHost, perIP: perIP, global: global}
}

func (l *Limits) Acquire(ctx context.Context, host, ip string) (func(), error) {
	if l.global != nil {
		if err := l.global.Wait(ctx); err != nil {
			return func() {}, err
		}
	}
	hostCh := l.chanFor(&l.hostSem, host, l.perHost)
	ipCh := l.chanFor(&l.ipSem, ip, l.perIP)
	select {
	case hostCh <- struct{}{}:
	case <-ctx.Done():
		return func() {}, ctx.Err()
	}
	select {
	case ipCh <- struct{}{}:
	case <-ctx.Done():
		<-hostCh
		return func() {}, ctx.Err()
	}
	return func() {
		<-ipCh
		<-hostCh
	}, nil
}

func (l *Limits) chanFor(m *sync.Map, key string, n int) chan struct{} {
	if key == "" {
		key = "_"
	}
	actual, _ := m.LoadOrStore(key, make(chan struct{}, n))
	return actual.(chan struct{})
}

func (l *Limits) HostInflight(host string) int {
	v, ok := l.hostSem.Load(host)
	if !ok {
		return 0
	}
	return len(v.(chan struct{}))
}
