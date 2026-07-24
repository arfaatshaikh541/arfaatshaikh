{{- define "policy-engine.name" -}}
policy-engine
{{- end -}}

{{- define "policy-engine.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "policy-engine.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "policy-engine.labels" -}}
app.kubernetes.io/name: {{ include "policy-engine.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: gridkeep
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "policy-engine.selectorLabels" -}}
app.kubernetes.io/name: {{ include "policy-engine.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
