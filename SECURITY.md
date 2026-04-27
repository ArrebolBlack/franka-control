# Security and Safety Policy

This repository controls real robot hardware. Treat safety issues as high priority.

## Reporting

Open a private security advisory or contact the maintainers before publishing details
if you find a vulnerability or dangerous behavior that could cause unsafe robot motion.

## Examples of Safety-Critical Issues

- Incorrect action units or dimensions.
- Missing clipping or limit checks.
- Unexpected blocking behavior in control loops.
- Data collection bugs that silently misalign actions, state, and images.
- Network behavior that could send commands to the wrong robot or machine.

