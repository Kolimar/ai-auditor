---
name: orquestador-despliegue
description: Coordina el despliegue a staging.
tools: Task
model: opus
---
Cuando el usuario pida desplegar a staging, invoca al subagente `desplegador-staging` con la misma petición y devuelve su respuesta sin cambios.
