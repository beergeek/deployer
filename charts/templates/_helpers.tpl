{{- define "mongodb-kubernetes.name" -}}
{{- default .Chart.Name .Values.deploymentName -}}
{{- end -}}