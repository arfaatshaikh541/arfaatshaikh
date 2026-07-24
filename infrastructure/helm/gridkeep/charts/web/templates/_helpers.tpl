{{- define "web.name" -}}
web
{{- end -}}

{{- define "web.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "web.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "web.labels" -}}
app.kubernetes.io/name: {{ include "web.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: gridkeep
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "web.selectorLabels" -}}
app.kubernetes.io/name: {{ include "web.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
