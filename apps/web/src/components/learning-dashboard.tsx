'use client';
import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { NOT_PUBLIC } from '@/lib/copy';

type Props = { locale: 'en' | 'ar' };
type Course = { slug: string; title: string; summary: string; intended_audience: string; estimated_minutes: number };
const copy = {
  en: { title: 'Learning', courses: 'Published courses', none: 'No course has been published yet. Courses appear here only after their content has passed review.', minutes: 'min', disclaimer: 'Course certificates are not an ijazah or scholarly qualification.' },
  ar: { title: 'التعلّم', courses: 'الدورات المنشورة', none: 'لم تُنشر أي دورة بعد. تظهر الدورات هنا بعد اجتياز محتواها للمراجعة.', minutes: 'دقيقة', disclaimer: 'شهادات الدورات ليست إجازة علمية ولا مؤهلاً شرعياً.' },
};
export function LearningDashboard({ locale }: Props) {
  const t = copy[locale];
  const [courses, setCourses] = useState<Course[] | null>(null);
  useEffect(() => { apiFetch<{ courses: Course[] }>('/learning/courses').then((r) => setCourses(r.courses)).catch(() => setCourses([])); }, []);
  return <main dir={locale === 'ar' ? 'rtl' : 'ltr'} aria-labelledby="learning-title" className="learning-dashboard">
    <header><h1 id="learning-title">{t.title}</h1></header>
    <section aria-labelledby="courses-title"><h2 id="courses-title">{t.courses}</h2>
      {courses === null && <p aria-busy="true">…</p>}
      {courses && courses.length === 0 && <div className="empty-state" role="status"><h3>{NOT_PUBLIC[locale]}</h3><p>{t.none}</p></div>}
      {courses?.map((c) => <article key={c.slug}><h3>{c.title}</h3><p>{c.summary}</p><small>{c.intended_audience} · {c.estimated_minutes} {t.minutes}</small></article>)}
    </section>
    <p role="note">{t.disclaimer}</p>
  </main>;
}
