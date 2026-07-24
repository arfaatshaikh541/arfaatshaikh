// Package energyprovider defines the narrow, provider-neutral grid-energy
// integration boundary Milestone 14 ("Energy-Aware Scheduling") requires --
// Provider is the abstraction the approved architecture's "mock energy
// provider" requirement asks for, a fixed interface a future adapter for a
// real grid-carbon-intensity feed (electricityMaps, WattTime, an operator's
// own utility contract) would implement once.
//
// Like internal/platform/billingprovider (and unlike
// internal/platform/clusteradapter/networkadapter, which are agent-side),
// Provider is verifier/integration-side: control-api itself holds and calls
// an implementation directly inside internal/modules/placement.EvaluatePlacement,
// because resolving a region's current grid conditions is inherently
// something the platform itself does when pricing and ranking a placement
// decision, not something delegated to a cluster agent.
//
// The only implementation in this codebase is MockProvider. No real grid-
// carbon-intensity API is reachable from this sandbox (the same category of
// constraint as MinIO/Docker Hub/a real payment gateway) -- it deterministically
// derives a plausible, illustrative carbon-intensity and renewable-mix signal
// from the region's own identity and the time of day, making no claim of
// reflecting any real electricity grid. A real provider (calling out to an
// actual grid-carbon API, handling its own auth and rate limits) is future
// work for whichever milestone integrates one.
package energyprovider

import (
	"context"
	"math"
	"time"

	"github.com/google/uuid"
)

// GridSnapshot is the narrow, provider-agnostic view of one region's current
// grid conditions a Provider resolves -- passed by value so this package has
// no database dependency of its own, mirroring billingprovider.Invoice's
// pattern.
type GridSnapshot struct {
	CarbonIntensityGPerKWh float64
	RenewablePercentage    float64
	AsOf                   time.Time
}

// Provider resolves the current grid carbon intensity and renewable mix for
// a region, as of a given time -- the time parameter exists so a caller can
// evaluate "what would this look like at the start of a proposed schedule
// window" as well as "right now", both without this package needing a clock
// of its own.
type Provider interface {
	FetchGridSnapshot(ctx context.Context, regionID uuid.UUID, asOf time.Time) (GridSnapshot, error)
}

// MockProvider fabricates a deterministic, time-varying grid signal: each
// region gets its own stable baseline carbon intensity (derived from a hash
// of its own UUID, so different regions plausibly differ from one another
// and repeated calls for the same region are stable), modulated by a smooth
// day/night cycle that is lowest at midday and highest at midnight -- loosely
// illustrative of solar generation's effect on grid mix, not a claim about
// any real region's actual grid.
type MockProvider struct{}

func NewMockProvider() *MockProvider { return &MockProvider{} }

func (p *MockProvider) FetchGridSnapshot(_ context.Context, regionID uuid.UUID, asOf time.Time) (GridSnapshot, error) {
	baseline := regionBaselineCarbonIntensity(regionID)
	hourFraction := float64(asOf.Hour())/24 + float64(asOf.Minute())/1440
	dayNightFactor := -0.3 * math.Cos(hourFraction*2*math.Pi) // low at midday, high at midnight
	carbonIntensity := baseline * (1 + dayNightFactor)
	carbonIntensity = clamp(carbonIntensity, 50, 900)

	// Illustrative inverse relationship: a cleaner (lower-carbon) grid is
	// modelled as having a higher renewable share.
	renewable := clamp(100-carbonIntensity/9, 5, 95)

	return GridSnapshot{
		CarbonIntensityGPerKWh: round2(carbonIntensity),
		RenewablePercentage:    round2(renewable),
		AsOf:                   asOf,
	}, nil
}

// regionBaselineCarbonIntensity derives a stable value in [150, 500] gCO2/kWh
// from the region's UUID bytes -- a simple, dependency-free hash (summing
// bytes, no crypto property needed) since all this requires is "different
// regions get different, but each region's own value never changes."
func regionBaselineCarbonIntensity(regionID uuid.UUID) float64 {
	var sum uint32
	for _, b := range regionID {
		sum = sum*31 + uint32(b)
	}
	return 150 + float64(sum%351)
}

func clamp(v, min, max float64) float64 {
	if v < min {
		return min
	}
	if v > max {
		return max
	}
	return v
}

func round2(v float64) float64 {
	return math.Round(v*100) / 100
}
