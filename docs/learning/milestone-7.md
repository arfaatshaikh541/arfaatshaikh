# Milestone 7: Governed Islamic Learning

## Implemented foundation

The learning hierarchy is `LearningPath -> Course -> CourseVersion -> CourseModule -> Lesson -> LessonSection`. Lesson claims link to governed `source_passages`; learner notes are private and ineligible as evidence.

## Publication policy

Publication requires governed evidence plus independent Islamic, editorial, and publisher approvals. An author cannot satisfy a required review. Published content may be archived or superseded, while revisions use course and lesson version fields.

## Translation integrity

Translations carry both structure and evidence fingerprints. Publication validation rejects translations that alter the canonical structure or evidence mapping.

## Assessment and progress

Objective grading is deterministic. Attempts, enrolments, lesson progress, resume position, time spent, score, and pass state are learner scoped. Generative religious grading is not included.

## Certificates

Certificates verify platform course completion only and carry a mandatory disclaimer that they are not an ijazah, scholarly qualification, or authority to issue rulings.

## Recommendations and children

Recommendations use language and prerequisite fit, not religiosity, sect, morality, or spiritual scoring. Child defaults fail closed when public profile, public certificate, or discussion access is enabled.

## Operational limits

This milestone provides production-oriented models, policies, migrations, contracts, and authenticated API primitives. Live PostgreSQL execution, browser end-to-end testing, email delivery, background jobs, and scholarly curriculum acceptance remain deployment gates.
