---
name: playful-mobile-ui
description: Design patterns for fun, playful, GenZ-oriented mobile apps that feel like a game/social app without visual overload. Use when building social, lifestyle, entertainment, or group-activity apps that need personality, warmth, and delight. Covers icon-first design, removing unnecessary text labels, empty state personality, visual hierarchy for fun contexts, gamification cues, and expressive yet clean UI.
---

# Playful Mobile UI

Design intelligence for mobile apps targeting younger audiences (GenZ/Millennial) that need to feel fun, social, and alive — without becoming cluttered or childish.

## When to Use

- Designing social/group activity apps (planning, voting, shared lists)
- Building lifestyle, entertainment, or gamified features
- Replacing boring, corporate-feeling UI with personality
- Improving empty states, loading states, and micro-copy
- Making filter/category selectors visually expressive
- Adding delight without clutter

## Core Philosophy

**Fun ≠ Noisy.** The goal is a UI that makes users smile without overwhelming them. Think: the warmth of a well-designed board game, not the chaos of a cluttered game UI.

### The 3 Pillars

1. **Icon-First, Text-Last** — Icons communicate faster than words. Labels are a fallback, not the default.
2. **Motion as Personality** — Static screens are dead screens. Subtle, purposeful motion creates life.
3. **Warm Whitespace** — Generous spacing with warm tones feels inviting, not empty.

## Design Rules

### 1. Icon-First Communication

| Pattern | Boring | Playful |
|---------|--------|---------|
| Price selector | `€ Barato / €€ Medio / €€€ Caro` | `💰 / 💰💰 / 💰💰💰` or coin icons only |
| Location filter | `🏠 Casa / 🌳 Exterior / 🏢 Interior` | Icon-only grid with icon + subtle tooltip on long-press |
| Time slot | `☀️ Mañana / 🌤 Tarde / 🌙 Noche` | Icon-only with time icon, label below ONLY if room |
| Repeat toggle | `"Repetible" / "Una vez"` | `↻` icon with checkmark overlay vs `1` badge |
| Category chips | `Text + icon` | Icon-only chips (28-36pt circles) with selection glow |

**Rule:** If an icon is universally understood (🏠, 💰, ☀️, 🌙), the text label is noise. Remove it.

### 2. Selector Patterns for Playful Apps

#### Pill/Chip Selectors (for 2-6 options)
```
[☀️] [🌤] [🌙]          ← icon-only, 44pt touch targets
 ╰── selected has:
     • Scale 1.1
     • Filled background (primary color)
     • Subtle bounce on tap
     • Glow/shadow ring
```

#### Coin/Star Selectors (for price/rating)
```
[🪙]  [🪙🪙]  [🪙🪙🪙]     ← stacking coins = intuitive price
 Free   $     $$              ← tiny subtitle ONLY if needed
```

#### Grid Selectors (for icons, categories)
```
┌────┐ ┌────┐ ┌────┐ ┌────┐
│ 🎵 │ │ 🍕 │ │ 🎬 │ │ 🏃 │    ← 4-column icon grid
└────┘ └────┘ └────┘ └────┘     ← selected = primary bg + scale
```

### 3. Empty States with Personality

**Boring:** "No hay planes. Crea uno para empezar."
**Playful:** Large playful illustration/icon + warm one-liner + immediate CTA

| Screen | Boring Empty | Playful Empty |
|--------|-------------|---------------|
| Box list | shippingbox icon + "Sin cajas todavía" | 📦✨ "¡Tu primera caja te espera!" + gradient CTA |
| Plan list | tray icon + "Sin planes" | 🎲 "¿Sin ideas? ¡Añade planes y deja que la suerte decida!" |
| History | clock icon + "Sin historial" | 🎉 "Aquí se guardan los mejores recuerdos" |
| Members | people icon + generic text | 👯 "¡Invita a tu crew!" |
| No filter results | tray icon | 🔍 "Hmm, nada por aquí... ¿quitamos filtros?" |

### 4. Visual Hierarchy for Fun

- **Hero elements** (dice, result card, main CTA): Large, bold, with glow/shadow
- **Secondary info** (metadata, dates): Small, muted, icon-prefixed
- **Selectors/filters**: Icon-forward, compact, visually grouped
- **Text content**: Use font weight hierarchy, not visual decorations

### 5. Color as Emotion

| Element | Static/Boring | Alive/Playful |
|---------|--------------|---------------|
| Selected state | Border + 15% opacity bg | Filled bg + subtle glow + scale |
| CTA button | Flat filled rectangle | Gradient fill + shadow + press scale |
| Result/Success | Green text | Confetti/sparkle icon + gradient card + bounce animation |
| Error | Red text | Warm rose + shake animation + haptic |
| Cards | Plain white bg | Subtle warm shadow + slight hover/press lift |

### 6. Micro-Copy Guidelines

- **Short.** Max 6-8 words per line of helper text.
- **Warm.** Use first person plural ("nuestro", "vamos") or exclamation marks sparingly.
- **No corpo-speak.** Replace "Crear nuevo elemento" → "¡A planear!" ; "Sin resultados" → "Nada por aquí 🤷"
- **Action-oriented labels.** "¡Lanzar!" not "Ejecutar randomizador"

### 7. Layout Density

- **Touch targets ≥ 44pt** — Non-negotiable
- **Filter chips:** Icon-only can go as small as 36pt circles in a tight grid
- **Card padding:** 16pt minimum, 20pt preferred
- **Section spacing:** 24-32pt between logical groups
- **Screen edge insets:** 20pt horizontal (never less on small phones)

### 8. Social/Group App Patterns

- **Member avatars:** Circular, stacked (overlapping -8pt) for group feel
- **Invitation flow:** Visual, not form-heavy. Big icon + single action CTA
- **Share actions:** Prominent, not buried in menus
- **Activity indicators:** "3 planes nuevos" badges, not just counts
- **Collaborative feel:** Use "we" language, show who did what with initials/avatars

## SwiftUI Implementation Patterns

### Icon-Only Filter Chip
```swift
struct IconChip: View {
    let icon: String
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.system(size: 18))
                .frame(width: 44, height: 44)
                .background(isSelected ? PBColors.primary.opacity(0.15) : PBColors.inputBackground)
                .foregroundStyle(isSelected ? PBColors.primary : .secondary)
                .clipShape(Circle())
                .overlay(Circle().stroke(isSelected ? PBColors.primary : .clear, lineWidth: 1.5))
                .scaleEffect(isSelected ? 1.08 : 1.0)
                .animation(.spring(duration: 0.25, bounce: 0.3), value: isSelected)
        }
    }
}
```

### Stacked Coin Price Selector
```swift
HStack(spacing: 6) {
    ForEach(0..<coinCount, id: \.self) { _ in
        Image(systemName: "bitcoinsign.circle.fill")
            .foregroundStyle(.orange)
    }
}
```

## Anti-Patterns

| Don't | Why | Do Instead |
|-------|-----|------------|
| Text labels on every icon | Cluttered, slow to scan | Icon-only with accessible label |
| Giant explanatory paragraphs | Nobody reads them | 1-line warm copy + visual |
| Monochrome/gray selectors | Boring, no personality | Colorful selected states with animation |
| Corporate empty states | Kills the fun mood | Playful copy + expressive icon/illustration |
| Over-the-top animations on everything | Feels exhausting/childish | Selective delight on key moments (result, success, first-use) |
| Using system default `.borderedProminent` everywhere | Generic iOS look | Custom gradient CTAs for primary actions |
| Emojis as icons in nav/toolbar | Inconsistent rendering | SF Symbols with personality (sparkle, dice, crown) |

## Checklist

- [ ] Selectors use icon-first design (text labels only where icon is ambiguous)
- [ ] Empty states have personality (playful copy + expressive visual)
- [ ] Primary CTA buttons use gradient + shadow + press feedback
- [ ] Cards have warm shadow, not pure black shadow
- [ ] At least 3 key moments have micro-animations (appear, select, result)
- [ ] No wall of text — helper text is ≤8 words
- [ ] Touch targets ≥ 44pt on all interactive elements
- [ ] Color conveys state (selected/unselected, success/error) with animation
- [ ] Filter chips compact and visually expressive
- [ ] Loading states are visual (shimmer/pulse), not "Cargando..."
