package com.sangam.app.ui

import android.app.Application
import android.graphics.Bitmap
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import android.graphics.Canvas
import androidx.compose.ui.unit.Density
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.sangam.app.ui.screens.CallInboxScreen
import com.sangam.app.ui.screens.DashboardScreen
import com.sangam.app.ui.screens.LoginScreen
import com.sangam.app.ui.screens.OnboardingWizardScreen
import com.sangam.app.ui.theme.SangamTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/**
 * Renders the main screens to PNG under build/screenshots/ so UI changes can be
 * reviewed without an emulator. Not a golden-image comparison: the files are for
 * people to look at. The window is tall so a whole scrolling screen fits in one image.
 *
 * Runs on a plain Application: SangamApp's encrypted token store needs the Android
 * keystore, which Robolectric does not provide. Network calls fail fast and the
 * screens show their offline state.
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
abstract class ScreenshotBase(private val variant: String, private val fontScale: Float) {
    @get:Rule
    val compose = createAndroidComposeRule<ComponentActivity>()

    private fun shoot(name: String, content: @Composable () -> Unit) {
        compose.setContent {
            val base = LocalDensity.current
            CompositionLocalProvider(LocalDensity provides Density(base.density, fontScale)) {
                SangamTheme(darkTheme = false) { content() }
            }
        }
        compose.waitForIdle()
        val out = File("build/screenshots/$variant/$name.png").apply { parentFile?.mkdirs() }
        // Draw the window in software; PixelCopy-based capture is not available on Robolectric.
        val view = compose.activity.window.decorView
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        view.draw(Canvas(bitmap))
        out.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    @Test fun login() = shoot("login") { LoginScreen(onLoginSuccess = {}) }
    @Test fun dashboard() = shoot("dashboard") { DashboardScreen() }
    @Test fun voiceAgentSetup() = shoot("voice_agent_setup") { OnboardingWizardScreen() }
    @Test fun callInbox() = shoot("call_inbox") { CallInboxScreen() }
}

/** A common budget phone in India, with the system font enlarged. */
@Config(application = Application::class, qualifiers = "w320dp-h3600dp-xhdpi", sdk = [34])
class SmallPhoneLargeFontScreenshotTest : ScreenshotBase("small_320dp_font130", 1.3f)

@Config(application = Application::class, qualifiers = "w360dp-h3600dp-xhdpi", sdk = [34])
class RegularPhoneScreenshotTest : ScreenshotBase("regular_360dp", 1.0f)
