{{- define "control-api.name" -}}
control-api
{{- end -}}

{{- define "control-api.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "control-api.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "control-api.labels" -}}
app.kubernetes.io/name: {{ include "control-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: gridkeep
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "control-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "control-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
