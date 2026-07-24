package networkadapter

import (
	"context"
	"testing"
)

func TestMockProvisionAndReleaseLifecycle(t *testing.T) {
	ctx := context.Background()
	m := NewMock()

	if err := m.ReleaseService(ctx, "res-1"); err == nil {
		t.Fatalf("expected an error releasing a reservation that was never provisioned")
	}

	if err := m.ProvisionService(ctx, "res-1", 10.5, "private-5g-standard"); err != nil {
		t.Fatalf("provision service: %v", err)
	}
	state, ok := m.GetServiceState("res-1")
	if !ok || state.BandwidthGbps != 10.5 || state.ServiceClass != "private-5g-standard" || state.Status != "provisioned" {
		t.Fatalf("expected a provisioned service, got %+v (exists=%v)", state, ok)
	}

	if err := m.ProvisionService(ctx, "res-1", 20, "private-5g-standard"); err != nil {
		t.Fatalf("re-provision service: %v", err)
	}
	if state, _ := m.GetServiceState("res-1"); state.BandwidthGbps != 20 {
		t.Fatalf("expected re-provisioning to overwrite bandwidth, got %v", state.BandwidthGbps)
	}

	if err := m.ProvisionService(ctx, "res-2", 0, "vpn"); err == nil {
		t.Fatalf("expected an error provisioning with non-positive bandwidth")
	}

	if err := m.ReleaseService(ctx, "res-1"); err != nil {
		t.Fatalf("release service: %v", err)
	}
	if state, _ := m.GetServiceState("res-1"); state.Status != "released" {
		t.Fatalf("expected status released, got %q", state.Status)
	}
}
