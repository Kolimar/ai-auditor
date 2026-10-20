# Split pre-registrado dev / holdout

Registrado **antes** de que existan los fixtures y antes de ver su contenido (2026-10-19).

Regla: un sistema o caso pertenece a **holdout** si `int(sha1(nombre).hexdigest(), 16) % 2 == 1`; si no, a **dev**.
Lo implementa `ai_auditor.evaluation.golden.split_of(name)`.

- **dev**: se pueden inspeccionar sus fallos para ajustar reglas.
- **holdout**: no se inspecciona durante el desarrollo; se mide al final y su resultado se reporta tal cual.
  Si después de medir el holdout se cambia alguna regla, el informe lo declara y el holdout deja de considerarse limpio.
