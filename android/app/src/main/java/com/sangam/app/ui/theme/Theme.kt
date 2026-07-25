package com.sangam.app.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat

val SangamBlue = Color(0xFF3B5BDB)
val SangamBlueDark = Color(0xFF25388E)
val SangamBlueLight = Color(0xFF91A7FF)

val ExpressifGreen = Color(0xFF2B9A6E)
val ExpressifOrange = Color(0xFFE67E22)
val ExpressifRed = Color(0xFFE74C3C)
val ExpressifPurple = Color(0xFF7C3AED)

private val LightColorScheme = lightColorScheme(
    primary = SangamBlue,
    onPrimary = Color.White,
    primaryContainer = SangamBlueLight,
    secondary = ExpressifGreen,
    tertiary = ExpressifPurple,
    background = Color(0xFFF8F9FA),
    surface = Color.White,
    error = ExpressifRed,
)

private val DarkColorScheme = darkColorScheme(
    primary = SangamBlueLight,
    onPrimary = Color.White,
    primaryContainer = SangamBlueDark,
    secondary = ExpressifGreen,
    tertiary = ExpressifPurple,
    background = Color(0xFF121212),
    surface = Color(0xFF1E1E1E),
    error = ExpressifRed,
)

val SangamTypography = Typography(
    displayLarge = TextStyle(
        fontWeight = FontWeight.Bold,
        fontSize = 36.sp,
        lineHeight = 44.sp,
    ),
    headlineLarge = TextStyle(
        fontWeight = FontWeight.Bold,
        fontSize = 28.sp,
        lineHeight = 36.sp,
    ),
    headlineMedium = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 24.sp,
        lineHeight = 32.sp,
    ),
    titleLarge = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 20.sp,
        lineHeight = 28.sp,
    ),
    titleMedium = TextStyle(
        fontWeight = FontWeight.Medium,
        fontSize = 16.sp,
        lineHeight = 24.sp,
    ),
    bodyLarge = TextStyle(
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        lineHeight = 24.sp,
    ),
    bodyMedium = TextStyle(
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 20.sp,
    ),
    labelLarge = TextStyle(
        fontWeight = FontWeight.Medium,
        fontSize = 14.sp,
        lineHeight = 20.sp,
    ),
)

@Composable
fun SangamTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
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
