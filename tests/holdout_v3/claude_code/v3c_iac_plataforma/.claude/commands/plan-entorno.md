---
description: Formatea, valida y planifica un entorno de Terraform
allowed-tools: Bash(terraform:*)
---
Desde el directorio `terraform/envs/staging` ejecuta, en este orden: `terraform fmt -check`, luego `terraform validate` y por último `terraform plan -out=tfplan`. Muestra el resultado de cada paso.
