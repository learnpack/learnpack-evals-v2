# ADR-0007 — Bootstrap del primer admin: allowlist de aprovisionamiento

**Estado:** aceptada · **Fecha:** 2026-07 · **Contexto:** Identity & Access (genérico)

## Contexto
El rol vive en `assessors.role` (nuestra DB), no en Clerk (ADR-0004). El MVP necesita al menos
una cuenta **admin** (registrar cursos, abrir campaña) y una **evaluador** antes del demo.

El único mecanismo existente (`app.cli set-role`, bloque 2) tiene un problema de arranque: exige
que la persona **ya se haya logueado** *y* que alguien corra un CLI **contra la DB de
producción**. Para un deploy en Render eso es fricción real.

La restricción a respetar: el bloque 2 dejó un invariante testeado —
`test_login_never_changes_the_role`, "authentication must not be able to escalate privileges".
Aplicar una allowlist en **cada** login lo rompería, y dejaría dos fuentes de verdad del rol
(¿sacar a alguien de la lista lo degrada en el próximo login?).

## Decisión
**`ADMIN_EMAILS` es una allowlist de *aprovisionamiento*, no de autorización.** Se aplica
**solo al crear** el `Assessor` (primer login) y nunca más.

| Situación | Resultado |
|---|---|
| Email en la lista, assessor **no existe** | se crea con `role='admin'` |
| Email en la lista, assessor **ya existe** como `evaluator` | **sigue** `evaluator` |
| Assessor `admin` existente, se lo **saca** de la lista | **sigue** `admin` |
| Sin claim `email` (falta el JWT template) | `evaluator` — degrada seguro |

Consecuencias del diseño:
1. **`assessors.role` sigue siendo la única fuente de verdad** una vez creada la fila. La env
   var se comporta como un *default de creación*, análogo a un seed — no como un permiso.
2. **El invariante se mantiene:** loguearse nunca cambia el rol de nadie.
3. **`app.cli set-role` sigue siendo el único modo de cambiar un rol** después de la creación.
4. Matching case-insensitive y con trim.

**Dependencia de seguridad explícita:** esto es seguro **porque el acceso es invite-only**
(ADR-0004): nadie puede registrarse con el email de un admin sin la invitación. Si alguna vez se
desactiva invite-only, esta allowlist se convierte en un vector de escalada y **hay que revisar
esta decisión**. Está anotado en el docstring de `ResolveAssessor._initial_role`.

## Consecuencias
- (+) Resuelve el arranque sin CLI contra producción: se setea `ADMIN_EMAILS` en Render y el
  primer login del owner ya es admin.
- (+) No introduce una segunda fuente de verdad ni rompe el invariante de no-escalada.
- (+) Cero cambios de schema; el resto del sistema no se entera.
- (−) El rol inicial depende de una env var: cambiarla exige redeploy. Aceptable, porque solo
  afecta a **cuentas que todavía no existen**.
- (−) Un admin creado por error hay que degradarlo con `set-role` (sacarlo de la lista no basta)
  — que es exactamente el comportamiento correcto.

## Alternativas consideradas
- **Allowlist aplicada en cada login** (propuesta inicial) → rechazada: rompe
  `test_login_never_changes_the_role` y duplica la fuente de verdad del rol.
- **Solo `set-role` (status quo)** → rechazada para el demo: exige login previo + CLI contra la
  DB de producción. Se mantiene como el mecanismo de cambio de roles.
- **Seed de una fila admin por email antes del primer login** → rechazada: `clerk_user_id` es
  `unique NOT NULL` y no se conoce hasta el primer login; obligaría a un linking por email, que
  es un vector peor.

## Implementación
`ADMIN_EMAILS` (CSV) → `Settings.bootstrap_admin_emails` → se inyecta en `ResolveAssessor`
desde `platform/security.py`. La regla vive en `ResolveAssessor._initial_role`.
Tests: `backend/tests/test_admin_bootstrap.py` (9 casos, incluidos los dos de no-escalada y
no-degradación).
