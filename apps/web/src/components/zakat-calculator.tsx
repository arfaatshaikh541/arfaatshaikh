"use client";
import { useState } from "react";

const FIELDS: [string, string, string][] = [
  ["cash", "Cash and bank balances", "النقد والأرصدة البنكية"],
  ["gold", "Gold (current market value)", "الذهب (بقيمته السوقية الحالية)"],
  ["silver", "Silver (current market value)", "الفضة (بقيمتها السوقية الحالية)"],
  ["investments", "Investments and trade goods", "الاستثمارات وعروض التجارة"],
  ["receivables", "Money owed to you (expected to be repaid)", "ديون لك مرجوّة السداد"],
  ["debts", "Debts you owe that are due now", "ديون عليك حالّة"],
];

export function ZakatCalculator({ locale }: { locale: "en" | "ar" }) {
  const ar = locale === "ar";
  const [v, setV] = useState<Record<string, string>>({});
  const [nisab, setNisab] = useState("");
  const n = (k: string) => Math.max(0, Number(v[k]) || 0);
  const net = n("cash") + n("gold") + n("silver") + n("investments") + n("receivables") - n("debts");
  const threshold = Number(nisab) || 0;
  const ready = threshold > 0;
  const due = ready && net >= threshold ? net * 0.025 : 0;
  const money = (x: number) => x.toLocaleString(locale, { maximumFractionDigits: 2 });
  return (
    <div className="governance-checker">
      <p className="tool-note">{ar ? "أدخل المبالغ بعملتك نفسها. لا يُرسل أي شيء إلى خادم." : "Enter amounts in a single currency. Nothing is sent to a server."}</p>
      <form className="governance-form" onSubmit={(e) => e.preventDefault()}>
        {FIELDS.map(([k, en, arName]) => (
          <label key={k}>{ar ? arName : en}
            <input type="number" min="0" step="any" inputMode="decimal" value={v[k] ?? ""} onChange={(e) => setV({ ...v, [k]: e.target.value })} />
          </label>
        ))}
        <label>{ar ? "قيمة النصاب بعملتك (ما يعادل ٨٥ غراماً من الذهب أو ٥٩٥ غراماً من الفضة بسعر اليوم)" : "Nisab in your currency (the value of 85 g of gold or 595 g of silver at today’s price)"}
          <input type="number" min="0" step="any" inputMode="decimal" value={nisab} onChange={(e) => setNisab(e.target.value)} />
        </label>
      </form>
      <p className="tool-value" role="status">
        {!ready ? (ar ? "أدخل قيمة النصاب لعرض النتيجة." : "Enter the nisab value to see the result.")
          : net >= threshold ? (ar ? `صافي مالك ${money(net)} يبلغ النصاب. الزكاة (٢٫٥٪): ${money(due)}` : `Your net wealth of ${money(net)} reaches the nisab. Zakat due (2.5%): ${money(due)}`)
          : (ar ? `صافي مالك ${money(net)} دون النصاب، فلا زكاة عليك حالياً.` : `Your net wealth of ${money(net)} is below the nisab, so no zakat is due at this time.`)}
      </p>
      <p className="tool-note">{ar ? "يفترض هذا الحساب مرور سنة هجرية كاملة على المال. تختلف آراء العلماء في بعض الأصناف (كالحلي والاستثمارات)، فاستشر عالماً موثوقاً. هذه ليست فتوى." : "This assumes a full lunar year (hawl) has passed on the wealth. Scholars differ on some categories (such as jewellery and investments), so consult a trusted scholar. This is not a fatwa."}</p>
    </div>
  );
}
