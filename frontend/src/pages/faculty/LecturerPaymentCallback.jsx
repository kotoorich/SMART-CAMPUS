import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Clock3, RefreshCw, ShieldAlert } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { verifyLecturerPayment } from "../../services/api";

export default function LecturerPaymentCallback() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [state, setState] = useState("checking");
  const [message, setMessage] = useState("Verifying your payment directly with the payment provider…");
  const reference = params.get("reference") || params.get("trxref");

  const verify = useCallback(async () => {
    if (!reference) {
      setState("failed");
      setMessage("The payment reference is missing. Contact the Smart Campus administrator.");
      return;
    }
    setState("checking");
    try {
      const result = await verifyLecturerPayment(reference);
      if (result.status === "paid") {
        setState("paid"); setMessage(result.message);
      } else {
        setState("pending"); setMessage(result.message || "The provider has not confirmed payment yet. You can retry verification.");
      }
    } catch (e) {
      setState("failed"); setMessage(e.message || "Payment verification could not be completed.");
    }
  }, [reference]);

  useEffect(() => { verify(); }, [verify]);

  return <main className="auth-screen"><section className="auth-card-wrap"><div className="auth-card text-center">
    <div className="auth-card-heading"><span className="auth-eyebrow">LECTURER REGISTRATION PAYMENT</span><h2>{state === "paid" ? "Payment confirmed." : state === "checking" ? "Checking payment." : state === "pending" ? "Payment not confirmed yet." : "Verification issue."}</h2><p>{message}</p></div>
    {state === "paid" ? <CheckCircle2 size={42} className="mx-auto text-emerald-600"/> : state === "checking" ? <Clock3 size={42} className="mx-auto text-blue-600"/> : <ShieldAlert size={42} className="mx-auto text-amber-600"/>}
    {reference && <p className="text-xs text-slate-500 mt-4 break-all">Reference: {reference}</p>}
    {state !== "paid" && <button className="auth-submit mt-5" onClick={verify}><RefreshCw size={16}/> Verify again</button>}
    <button className="auth-submit mt-3" onClick={() => navigate("/login?role=faculty")}>Continue to lecturer sign in</button>
    <p className="text-xs text-slate-500 mt-3">A successful payment does not activate the account automatically. Administrator staff verification is still required.</p>
  </div></section></main>;
}
