-- Security fix (post-Milestone-1 audit): track verification attempts per MFA
-- challenge. Without this column, a wrong TOTP guess raised an error inside
-- the same database transaction that had marked the challenge consumed,
-- causing the deferred rollback to undo the consumption -- so the challenge
-- stayed valid forever and could be retried without limit. attempt_count is
-- incremented and checked in its own committed transaction (see
-- identity.Service.VerifyMFAChallenge), independent of whether the code
-- being checked turns out to be valid.

ALTER TABLE mfa_challenges ADD COLUMN attempt_count INT NOT NULL DEFAULT 0;
