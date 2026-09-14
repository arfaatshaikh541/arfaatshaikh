from pathlib import Path

def test_bilingual_accessible_learning_route_exists():
 page=Path('../web/src/app/[locale]/learning/page.tsx').read_text()
 component=Path('../web/src/components/learning-dashboard.tsx').read_text()
 assert 'LearningDashboard' in page
 assert "dir={locale==='ar'?'rtl':'ltr'}" in component
 assert 'aria-labelledby' in component
 assert '<progress' in component
 assert 'not an ijazah' in component
