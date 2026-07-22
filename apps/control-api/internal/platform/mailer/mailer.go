// Package mailer sends transactional email (verification links, password
// reset links) over SMTP. In local development this points at Mailpit
// (docker-compose service `mailpit`), which captures mail without delivering
// it anywhere — never a production mail relay.
package mailer

import (
	"fmt"
	"net/smtp"
)

type Mailer struct {
	host string
	port string
	from string
}

func New(host, port, from string) *Mailer {
	return &Mailer{host: host, port: port, from: from}
}

func (m *Mailer) Send(to, subject, body string) error {
	addr := fmt.Sprintf("%s:%s", m.host, m.port)
	msg := fmt.Sprintf("From: %s\r\nTo: %s\r\nSubject: %s\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n%s\r\n",
		m.from, to, subject, body)

	if err := smtp.SendMail(addr, nil, m.from, []string{to}, []byte(msg)); err != nil {
		return fmt.Errorf("send mail to %s via %s: %w", to, addr, err)
	}
	return nil
}
