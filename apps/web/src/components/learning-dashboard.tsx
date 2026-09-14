'use client';

type Props = { locale: 'en' | 'ar' };
const copy = {
  en: { title: 'My learning', continueLabel: 'Continue learning', progress: 'Course progress', evidence: 'View lesson evidence', notes: 'Private notes', certificate: 'Certificates', disclaimer: 'Course certificates are not an ijazah or scholarly qualification.' },
  ar: { title: 'تعلّمي', continueLabel: 'متابعة التعلّم', progress: 'تقدّم الدورة', evidence: 'عرض أدلة الدرس', notes: 'ملاحظات خاصة', certificate: 'الشهادات', disclaimer: 'شهادات الدورات ليست إجازة علمية ولا مؤهلاً شرعياً.' },
};
export function LearningDashboard({ locale }: Props) {
 const t=copy[locale];
 return <main dir={locale==='ar'?'rtl':'ltr'} aria-labelledby="learning-title" className="learning-dashboard">
  <header><p>WORLD OF ISLAM</p><h1 id="learning-title">{t.title}</h1></header>
  <section aria-labelledby="continue-title"><h2 id="continue-title">{t.continueLabel}</h2><article><h3>Foundations of Islam</h3><label htmlFor="course-progress">{t.progress}: 0%</label><progress id="course-progress" max={100} value={0}>0%</progress><button type="button">{t.continueLabel}</button><details><summary>{t.evidence}</summary><p>No published lesson selected.</p></details></article></section>
  <nav aria-label={t.title}><a href="#notes">{t.notes}</a><a href="#certificates">{t.certificate}</a></nav>
  <p role="note">{t.disclaimer}</p>
 </main>;
}
