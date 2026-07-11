<?php
declare(strict_types=1);

/**
 * Contact form handler for static (shared-hosting) deployments.
 *
 * The site is exported as static HTML for hosts like IONOS shared hosting
 * that don't run a Node.js server, so the Next.js API route
 * (src/app/api/contact/route.ts, used for Node-capable deployments) is
 * replaced by this PHP script when statically exported. It mirrors the same
 * validation rules as src/lib/contact.ts and sends the enquiry by email
 * using PHP's built-in mail() function.
 *
 * CONFIGURE BEFORE GOING LIVE:
 *   1. Set $recipientEmail below to a real inbox.
 *   2. Many hosts (including IONOS) require the "From" address to be a
 *      mailbox that actually exists on your domain, or mail gets rejected
 *      or spam-flagged. If plain mail() proves unreliable, replace the
 *      send step with PHPMailer + your IONOS SMTP credentials instead —
 *      see https://github.com/PHPMailer/PHPMailer.
 */

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');

// ---- Configuration ---------------------------------------------------
$recipientEmail = 'hello@arfaat.com';
$recipientName = 'Arfaat Shaikh';

$rateLimitWindowSeconds = 10 * 60;
$rateLimitMaxRequests = 5;

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['message' => 'Method not allowed.']);
    exit;
}

// ---- Rate limiting (file-based, per IP) -------------------------------
// Shared hosting has no persistent key/value store available by default, so
// this uses the system temp directory (writable, outside the web root) as a
// simple sliding-window limiter. It resets if the host clears temp files —
// an acceptable trade-off for a low-traffic contact form. For higher
// traffic, move this to a real store your host provides (e.g. a database).
function contact_is_rate_limited(string $ip, int $windowSeconds, int $maxRequests): bool
{
    $dir = sys_get_temp_dir() . '/arfaat_contact_ratelimit';
    if (!is_dir($dir)) {
        @mkdir($dir, 0700, true);
    }
    $file = $dir . '/' . hash('sha256', $ip) . '.json';

    $now = time();
    $timestamps = [];
    if (is_file($file)) {
        $decoded = json_decode((string) file_get_contents($file), true);
        if (is_array($decoded)) {
            $timestamps = $decoded;
        }
    }
    $timestamps = array_values(array_filter(
        $timestamps,
        static fn ($t) => ($now - (int) $t) < $windowSeconds
    ));
    $timestamps[] = $now;
    @file_put_contents($file, json_encode($timestamps));

    return count($timestamps) > $maxRequests;
}

$ip = $_SERVER['HTTP_X_FORWARDED_FOR'] ?? $_SERVER['REMOTE_ADDR'] ?? 'unknown';
$ip = trim(explode(',', $ip)[0]);

if (contact_is_rate_limited($ip, $rateLimitWindowSeconds, $rateLimitMaxRequests)) {
    http_response_code(429);
    echo json_encode(['message' => 'Too many requests. Please try again in a few minutes.']);
    exit;
}

// ---- Read input ---------------------------------------------------------
// Accepts the JSON body the React form sends, with a form-encoded fallback.
$raw = file_get_contents('php://input');
$body = json_decode($raw !== false ? $raw : '', true);
if (!is_array($body)) {
    $body = $_POST;
}

function contact_field(array $body, string $key): string
{
    return isset($body[$key]) && is_scalar($body[$key]) ? trim((string) $body[$key]) : '';
}

$name = contact_field($body, 'name');
$email = contact_field($body, 'email');
$company = contact_field($body, 'company');
$phone = contact_field($body, 'phone');
$service = contact_field($body, 'service');
$budget = contact_field($body, 'budget');
$message = contact_field($body, 'message');
$preferredContact = contact_field($body, 'preferredContact');
$privacyConsent = !empty($body['privacyConsent']);
$website = contact_field($body, 'website'); // honeypot — real users never fill this in

// ---- Validate (mirrors src/lib/contact.ts) -------------------------------
$errors = [];
if (mb_strlen($name) < 2) {
    $errors['name'] = 'Enter your full name.';
}
if (!preg_match('/^[^\s@]+@[^\s@]+\.[^\s@]+$/', $email)) {
    $errors['email'] = 'Enter a valid email address.';
}
if ($service === '') {
    $errors['service'] = "Select the service you're interested in.";
}
if ($budget === '') {
    $errors['budget'] = 'Select an approximate budget range.';
}
if (mb_strlen($message) < 20) {
    $errors['message'] = 'Add a bit more detail about the project (at least 20 characters).';
}
if ($preferredContact === '') {
    $errors['preferredContact'] = "Select how you'd prefer to be contacted.";
}
if (!$privacyConsent) {
    $errors['privacyConsent'] = 'You must agree to the privacy policy to continue.';
}
if ($website !== '') {
    $errors['website'] = 'spam';
}

if (!empty($errors)) {
    if (isset($errors['website'])) {
        // Honeypot tripped: reject as generic spam without revealing why.
        http_response_code(400);
        echo json_encode(['message' => 'Unable to process this submission.']);
        exit;
    }
    http_response_code(422);
    echo json_encode(['message' => 'Please check the form for errors.', 'errors' => $errors]);
    exit;
}

// ---- Send email -----------------------------------------------------
// Strip newlines from anything that ends up in a header to prevent header
// injection via mail().
function contact_sanitize_header(string $value): string
{
    return trim((string) preg_replace('/[\r\n]+/', ' ', $value));
}

$safeName = contact_sanitize_header($name);
$safeEmail = contact_sanitize_header($email);
$safeCompany = $company !== '' ? contact_sanitize_header($company) : '—';
$safePhone = $phone !== '' ? contact_sanitize_header($phone) : '—';

$subject = "New enquiry from {$safeName}";

$bodyLines = [
    "Name: {$safeName}",
    "Email: {$safeEmail}",
    "Company: {$safeCompany}",
    "Phone: {$safePhone}",
    "Service: {$service}",
    "Budget: {$budget}",
    "Preferred contact method: {$preferredContact}",
    '',
    'Project description:',
    $message,
];
$emailBody = implode("\n", $bodyLines);

$headers = [
    // Change to a mailbox that exists on your own sending domain if your
    // host rejects or spam-flags mail sent "From" an address it doesn't own.
    "From: {$recipientName} <{$recipientEmail}>",
    "Reply-To: {$safeName} <{$safeEmail}>",
    'Content-Type: text/plain; charset=UTF-8',
];

$sent = @mail($recipientEmail, $subject, $emailBody, implode("\r\n", $headers));

if (!$sent) {
    http_response_code(502);
    echo json_encode([
        'message' => 'Something went wrong sending your message. Please try again or email directly.',
    ]);
    exit;
}

http_response_code(200);
echo json_encode(['message' => 'Thanks — your message has been received.']);
