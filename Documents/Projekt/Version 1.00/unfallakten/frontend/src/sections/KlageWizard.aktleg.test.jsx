import { useState } from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StepAktLeg } from "./KlageWizard.jsx";

function Wrapper({ gemountet = true }) {
  const [text, setText] = useState("");
  const [manuell, setManuell] = useState(false);
  const [aktLegTyp, setAktLegTyp] = useState("eigentum");

  return gemountet ? (
    <StepAktLeg
      aktLegTyp={aktLegTyp} onAktLegTyp={setAktLegTyp}
      aktLegFreigabe="freigabe" onAktLegFreigabe={() => {}}
      aktLegDatum="" onAktLegDatum={() => {}}
      mandantIstFahrer={false} mandantKz=""
      klaeger="Der Kläger"
      vorsteuer={false} unfalldatum="" unfallort=""
      beklagte={[]}
      auslandsunfall={false} onAuslandsunfall={() => {}}
      sachverhaltText={text} onSachverhaltText={setText}
      sachverhaltManuell={manuell} onSachverhaltManuell={setManuell}
    />
  ) : <div data-testid="leer" />;
}

describe("StepAktLeg – KW-25 Sachverhalt-Manuell-Flag im Section-State", () => {
  it("manueller Edit ueberlebt Remount", () => {
    const { rerender } = render(<Wrapper gemountet={true} />);

    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "MANUELL ERGÄNZT" } });
    expect(screen.getByRole("textbox").value).toBe("MANUELL ERGÄNZT");

    rerender(<Wrapper gemountet={false} />);
    expect(screen.getByTestId("leer")).toBeTruthy();

    rerender(<Wrapper gemountet={true} />);
    expect(screen.getByRole("textbox").value).toBe("MANUELL ERGÄNZT");
  });

  it("ohne Edit regeneriert Radio-Wechsel den Text", () => {
    render(<Wrapper gemountet={true} />);

    const textVorher = screen.getByRole("textbox").value;
    fireEvent.click(screen.getByText("Finanziert"));

    const textNachher = screen.getByRole("textbox").value;
    expect(textNachher).not.toBe(textVorher);
    expect(textNachher).toContain("finanzierenden Bank");
  });

  it("Reset-Knopf verwirft manuellen Text", () => {
    render(<Wrapper gemountet={true} />);

    const autoText = screen.getByRole("textbox").value;
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "MANUELL ERGÄNZT" } });
    expect(screen.getByRole("textbox").value).toBe("MANUELL ERGÄNZT");

    fireEvent.click(screen.getByRole("button", { name: /Neu generieren/i }));
    expect(screen.getByRole("textbox").value).toBe(autoText);

    fireEvent.click(screen.getByText("Finanziert"));
    expect(screen.getByRole("textbox").value).toContain("finanzierenden Bank");
  });
});
