import { describe, it, expect } from "vitest";
import { polleWorkerBisFertig } from "./ReviewQueueView.jsx";

const sofort = () => Promise.resolve();

describe("polleWorkerBisFertig (BUG-30)", () => {
  it("bricht ab, sobald die Komponente unmounted ist — keine weiteren Ticks", async () => {
    let montiert = true;
    let ticks = 0;
    const tick = async () => {
      ticks++;
      montiert = false; // Unmount waehrend des Polls (Dokumentwechsel)
      return { queue_status: "neu" };
    };
    const res = await polleWorkerBisFertig({
      tick,
      istMontiert: () => montiert,
      sleep: sofort,
      jetzt: () => 0, // Zeit steht -> nur der Abbruch beendet die Schleife
    });
    expect(res.status).toBe("abgebrochen");
    expect(ticks).toBe(1);
  });

  it("liefert 'fertig' mit Detail, wenn der Worker einen Endstatus meldet", async () => {
    const tick = async () => ({ queue_status: "bereit_zur_review" });
    const res = await polleWorkerBisFertig({
      tick,
      istMontiert: () => true,
      sleep: sofort,
      jetzt: () => 0,
    });
    expect(res.status).toBe("fertig");
    expect(res.detail.queue_status).toBe("bereit_zur_review");
  });

  it("liefert 'timeout', wenn die Zeit ohne Endstatus ablaeuft", async () => {
    const zeiten = [0, 0, 40000];
    let i = 0;
    const res = await polleWorkerBisFertig({
      tick: async () => ({ queue_status: "neu" }),
      istMontiert: () => true,
      sleep: sofort,
      jetzt: () => zeiten[Math.min(i++, zeiten.length - 1)],
    });
    expect(res.status).toBe("timeout");
  });

  it("liefert 'fehler', wenn ein Tick null liefert (laden fehlgeschlagen)", async () => {
    const res = await polleWorkerBisFertig({
      tick: async () => null,
      istMontiert: () => true,
      sleep: sofort,
      jetzt: () => 0,
    });
    expect(res.status).toBe("fehler");
  });
});
