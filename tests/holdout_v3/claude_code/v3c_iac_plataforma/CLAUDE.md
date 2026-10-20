# Plataforma de infraestructura

Repositorio Terraform + Kubernetes (Helm) de la plataforma. Toda la documentación operativa se pega aquí para que esté siempre a mano.

## Inventario de módulos

### modulo-01
Ruta: `terraform/modules/modulo-01`. Propietario: equipo-2. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_1`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-01. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-02
Ruta: `terraform/modules/modulo-02`. Propietario: equipo-3. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_2`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-01. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-03
Ruta: `terraform/modules/modulo-03`. Propietario: equipo-4. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_3`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-02. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-04
Ruta: `terraform/modules/modulo-04`. Propietario: equipo-5. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_4`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-03. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-05
Ruta: `terraform/modules/modulo-05`. Propietario: equipo-1. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_5`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-04. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-06
Ruta: `terraform/modules/modulo-06`. Propietario: equipo-2. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_6`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-05. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-07
Ruta: `terraform/modules/modulo-07`. Propietario: equipo-3. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_7`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-06. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-08
Ruta: `terraform/modules/modulo-08`. Propietario: equipo-4. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_8`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-07. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-09
Ruta: `terraform/modules/modulo-09`. Propietario: equipo-5. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_9`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-08. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-10
Ruta: `terraform/modules/modulo-10`. Propietario: equipo-1. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_10`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-09. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-11
Ruta: `terraform/modules/modulo-11`. Propietario: equipo-2. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_11`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-10. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-12
Ruta: `terraform/modules/modulo-12`. Propietario: equipo-3. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_12`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-11. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-13
Ruta: `terraform/modules/modulo-13`. Propietario: equipo-4. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_13`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-12. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-14
Ruta: `terraform/modules/modulo-14`. Propietario: equipo-5. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_14`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-13. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-15
Ruta: `terraform/modules/modulo-15`. Propietario: equipo-1. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_15`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-14. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-16
Ruta: `terraform/modules/modulo-16`. Propietario: equipo-2. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_16`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-15. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-17
Ruta: `terraform/modules/modulo-17`. Propietario: equipo-3. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_17`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-16. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-18
Ruta: `terraform/modules/modulo-18`. Propietario: equipo-4. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_18`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-17. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-19
Ruta: `terraform/modules/modulo-19`. Propietario: equipo-5. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_19`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-18. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-20
Ruta: `terraform/modules/modulo-20`. Propietario: equipo-1. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_20`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-19. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-21
Ruta: `terraform/modules/modulo-21`. Propietario: equipo-2. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_21`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-20. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-22
Ruta: `terraform/modules/modulo-22`. Propietario: equipo-3. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_22`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-21. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-23
Ruta: `terraform/modules/modulo-23`. Propietario: equipo-4. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_23`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-22. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-24
Ruta: `terraform/modules/modulo-24`. Propietario: equipo-5. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_24`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-23. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-25
Ruta: `terraform/modules/modulo-25`. Propietario: equipo-1. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_25`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-24. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-26
Ruta: `terraform/modules/modulo-26`. Propietario: equipo-2. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_26`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-25. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-27
Ruta: `terraform/modules/modulo-27`. Propietario: equipo-3. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_27`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-26. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-28
Ruta: `terraform/modules/modulo-28`. Propietario: equipo-4. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_28`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-27. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-29
Ruta: `terraform/modules/modulo-29`. Propietario: equipo-5. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_29`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-28. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-30
Ruta: `terraform/modules/modulo-30`. Propietario: equipo-1. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_30`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-29. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-31
Ruta: `terraform/modules/modulo-31`. Propietario: equipo-2. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_31`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-30. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-32
Ruta: `terraform/modules/modulo-32`. Propietario: equipo-3. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_32`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-31. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-33
Ruta: `terraform/modules/modulo-33`. Propietario: equipo-4. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_33`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-32. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-34
Ruta: `terraform/modules/modulo-34`. Propietario: equipo-5. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_34`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-33. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-35
Ruta: `terraform/modules/modulo-35`. Propietario: equipo-1. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_35`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-34. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-36
Ruta: `terraform/modules/modulo-36`. Propietario: equipo-2. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_36`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-35. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-37
Ruta: `terraform/modules/modulo-37`. Propietario: equipo-3. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_37`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-36. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-38
Ruta: `terraform/modules/modulo-38`. Propietario: equipo-4. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_38`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-37. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-39
Ruta: `terraform/modules/modulo-39`. Propietario: equipo-5. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_39`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-38. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-40
Ruta: `terraform/modules/modulo-40`. Propietario: equipo-1. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_40`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-39. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-41
Ruta: `terraform/modules/modulo-41`. Propietario: equipo-2. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_41`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-40. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-42
Ruta: `terraform/modules/modulo-42`. Propietario: equipo-3. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_42`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-41. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-43
Ruta: `terraform/modules/modulo-43`. Propietario: equipo-4. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_43`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-42. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-44
Ruta: `terraform/modules/modulo-44`. Propietario: equipo-5. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_44`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-43. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-45
Ruta: `terraform/modules/modulo-45`. Propietario: equipo-1. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_45`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-44. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-46
Ruta: `terraform/modules/modulo-46`. Propietario: equipo-2. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_46`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-45. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-47
Ruta: `terraform/modules/modulo-47`. Propietario: equipo-3. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_47`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-46. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-48
Ruta: `terraform/modules/modulo-48`. Propietario: equipo-4. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_48`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-47. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-49
Ruta: `terraform/modules/modulo-49`. Propietario: equipo-5. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_49`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-48. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-50
Ruta: `terraform/modules/modulo-50`. Propietario: equipo-1. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_50`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-49. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-51
Ruta: `terraform/modules/modulo-51`. Propietario: equipo-2. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_51`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-50. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-52
Ruta: `terraform/modules/modulo-52`. Propietario: equipo-3. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_52`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-51. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-53
Ruta: `terraform/modules/modulo-53`. Propietario: equipo-4. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_53`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-52. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-54
Ruta: `terraform/modules/modulo-54`. Propietario: equipo-5. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_54`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-53. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-55
Ruta: `terraform/modules/modulo-55`. Propietario: equipo-1. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_55`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-54. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-56
Ruta: `terraform/modules/modulo-56`. Propietario: equipo-2. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_56`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-55. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-57
Ruta: `terraform/modules/modulo-57`. Propietario: equipo-3. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_57`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-56. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-58
Ruta: `terraform/modules/modulo-58`. Propietario: equipo-4. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_58`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-57. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-59
Ruta: `terraform/modules/modulo-59`. Propietario: equipo-5. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_59`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-58. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

### modulo-60
Ruta: `terraform/modules/modulo-60`. Propietario: equipo-1. Variables: `nombre`, `entorno`, `region`, `etiquetas`, `cidr_60`. Salidas: `id`, `arn`, `endpoint`. Dependencias: modulo-59. Notas: se despliega primero en `dev`, luego `staging` y por último `prod` tras aprobación del responsable; no cambiar el nombre de recursos con estado porque fuerza recreación.

## Política de cambios

1. Regla 1: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 2 días de antelación cuando afecte a servicios con SLA.
2. Regla 2: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 3 días de antelación cuando afecte a servicios con SLA.
3. Regla 3: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 4 días de antelación cuando afecte a servicios con SLA.
4. Regla 4: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 5 días de antelación cuando afecte a servicios con SLA.
5. Regla 5: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 6 días de antelación cuando afecte a servicios con SLA.
6. Regla 6: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 7 días de antelación cuando afecte a servicios con SLA.
7. Regla 7: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 1 días de antelación cuando afecte a servicios con SLA.
8. Regla 8: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 2 días de antelación cuando afecte a servicios con SLA.
9. Regla 9: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 3 días de antelación cuando afecte a servicios con SLA.
10. Regla 10: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 4 días de antelación cuando afecte a servicios con SLA.
11. Regla 11: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 5 días de antelación cuando afecte a servicios con SLA.
12. Regla 12: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 6 días de antelación cuando afecte a servicios con SLA.
13. Regla 13: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 7 días de antelación cuando afecte a servicios con SLA.
14. Regla 14: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 1 días de antelación cuando afecte a servicios con SLA.
15. Regla 15: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 2 días de antelación cuando afecte a servicios con SLA.
16. Regla 16: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 3 días de antelación cuando afecte a servicios con SLA.
17. Regla 17: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 4 días de antelación cuando afecte a servicios con SLA.
18. Regla 18: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 5 días de antelación cuando afecte a servicios con SLA.
19. Regla 19: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 6 días de antelación cuando afecte a servicios con SLA.
20. Regla 20: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 7 días de antelación cuando afecte a servicios con SLA.
21. Regla 21: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 1 días de antelación cuando afecte a servicios con SLA.
22. Regla 22: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 2 días de antelación cuando afecte a servicios con SLA.
23. Regla 23: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 3 días de antelación cuando afecte a servicios con SLA.
24. Regla 24: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 4 días de antelación cuando afecte a servicios con SLA.
25. Regla 25: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 5 días de antelación cuando afecte a servicios con SLA.
26. Regla 26: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 6 días de antelación cuando afecte a servicios con SLA.
27. Regla 27: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 7 días de antelación cuando afecte a servicios con SLA.
28. Regla 28: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 1 días de antelación cuando afecte a servicios con SLA.
29. Regla 29: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 2 días de antelación cuando afecte a servicios con SLA.
30. Regla 30: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 3 días de antelación cuando afecte a servicios con SLA.
31. Regla 31: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 4 días de antelación cuando afecte a servicios con SLA.
32. Regla 32: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 5 días de antelación cuando afecte a servicios con SLA.
33. Regla 33: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 6 días de antelación cuando afecte a servicios con SLA.
34. Regla 34: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 7 días de antelación cuando afecte a servicios con SLA.
35. Regla 35: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 1 días de antelación cuando afecte a servicios con SLA.
36. Regla 36: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 2 días de antelación cuando afecte a servicios con SLA.
37. Regla 37: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 3 días de antelación cuando afecte a servicios con SLA.
38. Regla 38: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 4 días de antelación cuando afecte a servicios con SLA.
39. Regla 39: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 5 días de antelación cuando afecte a servicios con SLA.
40. Regla 40: todo cambio en infraestructura de producción requiere revisión de dos personas, un plan adjunto al PR y una ventana de mantenimiento comunicada en el canal #plataforma con al menos 6 días de antelación cuando afecte a servicios con SLA.

## Convenciones

- Nombres en minúsculas con guiones.
- Estado remoto en S3 con bloqueo en DynamoDB.
- Nunca ejecutar `terraform apply` sin plan guardado.
