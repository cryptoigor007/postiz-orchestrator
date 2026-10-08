# Applied: emilkowalski/skills

Source: https://github.com/emilkowalski/skills

Used for WebApp polish:
- **emil-design-eng** — ease-out curves, press scale 0.97, no scale(0) enters, UI <300ms, interruptible transitions
- **apple-design** — materials/blur hierarchy, instant press feedback, reduced-motion, spatial consistency

Install for agents: `npx skills@latest add emilkowalski/skills`

## Установлено (2026-09-23)

```
npx skills@latest add emilkowalski/skills -g -y --agent '*'
```

Ставится в `~/.agents/skills` (DSH читает этот каталог: `~/.agents/skills`, `~/.dsh/skills`).
Появилось 13 скиллов; для панели важны `emil-design-eng`, `apple-design`, `mobile-native`
(+ `animate`, `review-animations`, `improve-animations`, `find-animation-opportunities`,
`animation-vocabulary`, `prototype`, `pick-ui-library`). Не относятся к проекту: `write-swift`,
`animate-expo`, `ask-sonner` (Swift/Expo/React), их не используем.
Проверка: каталог скиллов сессии сразу показывает установленное — значит, подключение работает.

