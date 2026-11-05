{{- define "tuos.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "tuos.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "tuos.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "tuos.selectorLabels" -}}
app.kubernetes.io/name: {{ include "tuos.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "tuos.labels" -}}
helm.sh/chart: {{ include "tuos.chart" . }}
{{ include "tuos.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "tuos.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "tuos.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/* The Secret the pod's environment comes from: the user's, or the one this chart creates. */}}
{{- define "tuos.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else if .Values.secrets.env }}
{{- include "tuos.fullname" . }}
{{- end }}
{{- end }}

{{/* Where the pinned config.yaml is mounted. /etc/hermes is taken: the image keeps build facts there. */}}
{{- define "tuos.managedDir" -}}
/etc/hermes-managed
{{- end }}

{{/* The container's env entries (a YAML list, unindented), or nothing. */}}
{{- define "tuos.env" -}}
{{- if .Values.config }}
- name: HERMES_MANAGED_DIR
  value: {{ include "tuos.managedDir" . }}
{{- end }}
{{- if .Values.dashboard.enabled }}
- name: HERMES_DASHBOARD
  value: "1"
- name: HERMES_DASHBOARD_HOST
  value: {{ ternary "0.0.0.0" "127.0.0.1" .Values.dashboard.expose | quote }}
- name: HERMES_DASHBOARD_PORT
  value: {{ .Values.dashboard.port | quote }}
{{- end }}
{{- with .Values.env }}
{{ toYaml . }}
{{- end }}
{{- end }}
