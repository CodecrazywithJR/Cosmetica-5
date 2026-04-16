---
name: swiftui-animator
description: SwiftUI motion design, micro-interactions, transitions, and animation patterns. Use when building or improving animations, transitions, haptic feedback, scroll effects, or any motion-related UI in SwiftUI iOS apps. Covers spring physics, matched geometry, phase animators, keyframe animators, gesture-driven motion, stagger effects, and accessibility (reduced motion).
---

# SwiftUI Animator

Procedural knowledge for creating polished, performant SwiftUI animations that feel native and delightful.

## When to Use

- Adding appear/disappear transitions to views
- Creating micro-interactions (button press, toggle, selection feedback)
- Building scroll-driven animations or parallax effects
- Implementing staggered list animations
- Adding gesture-driven motion (drag, swipe, long press)
- Polishing loading states, skeleton screens, shimmer effects
- Creating playful UI elements (bouncy, springy, elastic)
- Validating animation accessibility (prefers-reduced-motion)

## Core Principles

1. **Motion = Meaning** — Every animation must communicate something (state change, spatial relationship, feedback). Never animate just for decoration.
2. **Native Feel** — Match iOS system animation curves. Prefer `.spring()` over `.easeInOut` for interactive elements.
3. **Budget 250ms** — Most micro-interactions should complete in 150-300ms. Longer than 500ms feels sluggish.
4. **Respect Reduced Motion** — Always check `@Environment(\.accessibilityReduceMotion)` and provide instant alternatives.
5. **GPU-friendly** — Animate opacity, scale, offset, rotation. Avoid animating frame size or complex layout recalculations.

## Animation Timing Reference

| Interaction | Duration | Curve | Example |
|-------------|----------|-------|---------|
| Button press feedback | 80-150ms | `.easeOut` | Scale 0.95 → 1.0 |
| View appear | 300-500ms | `.spring(duration: 0.5, bounce: 0.3)` | Fade + slide up |
| View dismiss | 200-300ms | `.easeIn` | Fade + slide down (exit faster than enter) |
| Selection toggle | 150-250ms | `.spring(duration: 0.3, bounce: 0.2)` | Color/border change |
| Stagger delay per item | 50-80ms | Same as parent | List items cascade |
| Loading shimmer | 1.5-2s loop | `.easeInOut.repeatForever` | Gradient sweep |
| Dice/slot spin | 800-1200ms | `.spring(duration: 1, bounce: 0.15)` | Rotation + bounce |
| Success celebration | 400-600ms | `.spring(bounce: 0.5)` | Scale pop + confetti |

## SwiftUI Animation APIs

### Springs (preferred for interactive UI)

```swift
// Modern spring — use this by default
.animation(.spring(duration: 0.4, bounce: 0.3), value: isExpanded)

// Bouncy spring for playful elements
.animation(.spring(duration: 0.5, bounce: 0.5), value: isSelected)

// Snappy spring for quick feedback
.animation(.snappy(duration: 0.25), value: tabIndex)

// Interactive spring for gesture-driven
.animation(.interactiveSpring(duration: 0.3), value: dragOffset)
```

### Appear/Disappear Pattern

```swift
struct AppearAnimationView: View {
    @State private var appeared = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        content
            .opacity(appeared ? 1 : 0)
            .offset(y: appeared ? 0 : 20)
            .onAppear {
                guard !reduceMotion else { appeared = true; return }
                withAnimation(.spring(duration: 0.5, bounce: 0.3).delay(0.1)) {
                    appeared = true
                }
            }
    }
}
```

### Stagger Effect for Lists

```swift
ForEach(Array(items.enumerated()), id: \.element.id) { index, item in
    ItemRow(item: item)
        .opacity(appeared ? 1 : 0)
        .offset(y: appeared ? 0 : 16)
        .animation(
            .spring(duration: 0.4, bounce: 0.2)
            .delay(Double(index) * 0.06),
            value: appeared
        )
}
```

### Transition Combos

```swift
// Slide + fade (for sheets/modals)
.transition(.move(edge: .bottom).combined(with: .opacity))

// Scale pop (for result cards, celebrations)
.transition(.scale(scale: 0.8).combined(with: .opacity))

// Asymmetric (enter slow, exit fast)
.transition(.asymmetric(
    insertion: .opacity.combined(with: .offset(y: 20)).animation(.spring(duration: 0.5)),
    removal: .opacity.animation(.easeIn(duration: 0.2))
))
```

### Phase Animator (iOS 17+)

```swift
// Continuous pulse effect
.phaseAnimator([false, true]) { content, phase in
    content
        .scaleEffect(phase ? 1.05 : 1.0)
        .shadow(radius: phase ? 12 : 6)
} animation: { _ in
    .easeInOut(duration: 1.5)
}
```

### Shimmer / Skeleton Loading

```swift
struct ShimmerModifier: ViewModifier {
    @State private var phase: CGFloat = -1
    
    func body(content: Content) -> some View {
        content.overlay(
            LinearGradient(
                colors: [.clear, .white.opacity(0.4), .clear],
                startPoint: .leading, endPoint: .trailing
            )
            .offset(x: phase * 200)
            .mask(content)
        )
        .onAppear {
            withAnimation(.linear(duration: 1.5).repeatForever(autoreverses: false)) {
                phase = 1
            }
        }
    }
}
```

### Haptic Pairing

Always pair animations with appropriate haptics:
- **Selection change** → `UISelectionFeedbackGenerator` (light tick)
- **Button tap** → `UIImpactFeedbackGenerator(.light)` or `.medium`
- **Success** → `UINotificationFeedbackGenerator(.success)`
- **Error** → `UINotificationFeedbackGenerator(.error)`
- **Dice roll/slot machine** → Multiple `.medium` impacts during spin, `.success` on result

## Anti-Patterns

| Don't | Why | Do Instead |
|-------|-----|------------|
| Animate frame/size changes | Causes layout thrashing | Animate scale, offset, opacity |
| Use `withAnimation` on every state change | Over-animation feels chaotic | Be selective — only key interactions |
| Ignore `accessibilityReduceMotion` | Accessibility violation | Provide instant fallback |
| Chain > 3 sequential animations | User loses attention | Use parallel or stagger |
| Use `.linear` for UI motion | Feels robotic, unnatural | Use `.spring` or `.easeOut` |
| Animate onAppear in ScrollView lazily | Items pop in distractingly | Pre-set appeared state or use offset threshold |
| Add bounce > 0.6 | Feels cartoonish/childish | Keep bounce 0.2-0.4 for playful, 0.1-0.2 for refined |

## Checklist

- [ ] All interactive elements have press feedback (scale, opacity, or color change within 150ms)
- [ ] View appear animations use spring curves with reduced-motion fallback
- [ ] Exit animations are faster than enter animations
- [ ] List stagger delay is 50-80ms per item (max ~400ms total for visible items)
- [ ] Loading states have shimmer or subtle pulse, not just a spinner
- [ ] Success/error states have matching haptic feedback
- [ ] No animation exceeds 600ms for micro-interactions
- [ ] `.animation()` is value-scoped (not bare `.animation(.spring())`)
