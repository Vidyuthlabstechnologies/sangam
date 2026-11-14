package com.sangam.app.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat

// Pure White & Editorial Monochrome Palette (Zero Green / Zero Blue)
val SangamObsidian = Color(0xFF09090B)
val SangamCharcoal = Color(0xFF18181B)
val SangamGraphite = Color(0xFF27272A)
val SangamZinc = Color(0xFF52525B)
val SangamMuted = Color(0xFF71717A)
val SangamBorder = Color(0xFFE4E4E7)
val SangamAlabaster = Color(0xFFF8F8F7)
val SangamPureWhite = Color(0xFFFFFFFF)
val SangamTerracotta = Color(0xFFD97706)
val SangamCrimson = Color(0xFFDC2626)

private val LightColorScheme = lightColorScheme(
    primary = SangamObsidian,
    onPrimary = SangamPureWhite,
    primaryContainer = SangamAlabaster,
    onPrimaryContainer = SangamObsidian,
    secondary = SangamGraphite,
    onSecondary = SangamPureWhite,
    secondaryContainer = Color(0xFFF4F4F5),
    onSecondaryContainer = SangamObsidian,
    tertiary = SangamTerracotta,
    onTertiary = SangamPureWhite,
    background = SangamPureWhite,
    onBackground = SangamObsidian,
    surface = SangamPureWhite,
    onSurface = SangamObsidian,
    surfaceVariant = SangamAlabaster,
    onSurfaceVariant = SangamZinc,
    // Outline marks interactive edges (text fields, outlined buttons, an off switch's thumb)
    // and needs 3:1 against white. E4E4E7 was 1.2:1, so an off switch was nearly invisible.
    // Purely decorative lines (dividers) use outlineVariant.
    outline = SangamMuted,
    outlineVariant = SangamBorder,
    error = SangamCrimson,
    // M3's default surfaceContainer* tokens are lilac. Cards, sheets, menus and the
    // bottom bar read them, which tinted the whole app purple. Neutral zinc instead.
    surfaceContainerLowest = SangamPureWhite,
    surfaceContainerLow = Color(0xFFFAFAFA),
    surfaceContainer = Color(0xFFF7F7F8),
    surfaceContainerHigh = Color(0xFFF4F4F5),
    // Filled cards use this one, so it stays a light wash rather than a grey slab.
    surfaceContainerHighest = Color(0xFFF1F1F3),
    surfaceTint = Color.Transparent,
)

private val DarkColorScheme = darkColorScheme(
    primary = SangamPureWhite,
    onPrimary = SangamObsidian,
    primaryContainer = SangamGraphite,
    onPrimaryContainer = SangamPureWhite,
    secondary = Color(0xFFD4D4D8),
    onSecondary = SangamObsidian,
    tertiary = SangamTerracotta,
    background = SangamObsidian,
    onBackground = SangamPureWhite,
    surface = SangamCharcoal,
    onSurface = SangamPureWhite,
    surfaceVariant = SangamGraphite,
    onSurfaceVariant = Color(0xFFA1A1AA),
    outline = Color(0xFF71717A),
    outlineVariant = Color(0xFF3F3F46),
    error = SangamCrimson,
    surfaceContainerLowest = SangamObsidian,
    surfaceContainerLow = Color(0xFF141416),
    surfaceContainer = SangamCharcoal,
    surfaceContainerHigh = Color(0xFF202023),
    surfaceContainerHighest = SangamGraphite,
    surfaceTint = Color.Transparent,
)

val SangamTypography = Typography(
    displayLarge = TextStyle(
        fontWeight = FontWeight.Bold,
        fontSize = 34.sp,
        lineHeight = 40.sp,
        letterSpacing = (-0.8).sp,
    ),
    headlineLarge = TextStyle(
        fontWeight = FontWeight.Bold,
        fontSize = 26.sp,
        lineHeight = 32.sp,
        letterSpacing = (-0.5).sp,
    ),
    headlineMedium = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 20.sp,
        lineHeight = 28.sp,
        letterSpacing = (-0.3).sp,
    ),
    titleLarge = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 18.sp,
        lineHeight = 24.sp,
    ),
    titleMedium = TextStyle(
        fontWeight = FontWeight.Medium,
        fontSize = 15.sp,
        lineHeight = 22.sp,
    ),
    bodyLarge = TextStyle(
        fontWeight = FontWeight.Normal,
        fontSize = 15.sp,
        lineHeight = 22.sp,
    ),
    bodyMedium = TextStyle(
        fontWeight = FontWeight.Normal,
        fontSize = 13.sp,
        lineHeight = 19.sp,
    ),
    labelLarge = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 13.sp,
        lineHeight = 18.sp,
    ),
)

@Composable
fun SangamTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    // Default to editorial pure-white light mode unless explicitly overridden
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme
    val view = LocalView.current

    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.surface.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = SangamTypography,
        content = content,
    )
}
