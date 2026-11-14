package com.sangam.app.ui

import android.app.Application
import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.activity.ComponentActivity
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.Density
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.sangam.app.ui.screens.*
import com.sangam.app.ui.theme.SangamTheme
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/**
 * Renders every screen to PNG under build/screenshots/ so UI changes can be reviewed
 * without an emulator. Not a golden-image comparison: the files are for people to look at.
 * The window is tall so a whole scrolling screen fits in one image.
 *
 * A local fake backend ([FakeBackend]) serves sample data, so lists and cards are filled.
 * Runs on a plain Application: SangamApp's encrypted token store needs the Android keystore,
 * which Robolectric does not provide.
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
abstract class ScreenshotBase(private val variant: String, private val fontScale: Float) {
    @get:Rule
    val compose = createAndroidComposeRule<ComponentActivity>()

    @Before
    fun backend() = FakeBackend.start(ApplicationProvider.getApplicationContext())

    private fun shoot(name: String, content: @Composable () -> Unit) {
        compose.setContent {
            val base = LocalDensity.current
            CompositionLocalProvider(LocalDensity provides Density(base.density, fontScale)) {
                SangamTheme(darkTheme = false) { content() }
            }
        }
        // Let the fake network answer and the screen recompose with the data.
        repeat(15) {
            Thread.sleep(100)
            compose.waitForIdle()
        }
        val out = File("build/screenshots/$variant/$name.png").apply { parentFile?.mkdirs() }
        // Draw the window in software; PixelCopy-based capture is not available on Robolectric.
        val view = compose.activity.window.decorView
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        view.draw(Canvas(bitmap))
        out.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    @Test fun login() = shoot("01_login") { LoginScreen(onLoginSuccess = {}) }
    @Test fun dashboard() = shoot("02_dashboard") { DashboardScreen() }
    @Test fun voiceAgentSetup() = shoot("03_voice_agent_setup") { OnboardingWizardScreen() }
    @Test fun callInbox() = shoot("04_call_inbox") { CallInboxScreen() }
    @Test fun voiceAgents() = shoot("05_voice_agents") { VoiceAgentsScreen() }
    @Test fun workflows() = shoot("06_workflows") { WorkflowListScreen(onWorkflowClick = {}, onVoiceCreate = {}) }
    @Test fun workflowDetail() = shoot("07_workflow_detail") { WorkflowDetailScreen(workflowId = "wf1", onBack = {}) }
    @Test fun approvals() = shoot("08_approvals") { ApprovalsScreen(onWorkflowClick = {}) }
    @Test fun people() = shoot("09_people") { ActorsScreen() }
    @Test fun aiAssistant() = shoot("10_ai_assistant") { AIAssistantScreen() }
    @Test fun voiceWorkflow() = shoot("11_voice_workflow") { VoiceWorkflowScreen() }
    @Test fun vendors() = shoot("12_vendors") { VendorListScreen(onVendorClick = {}, onAddVendor = {}) }
    @Test fun vendorDetail() = shoot("13_vendor_detail") {
        VendorDetailScreen(vendorId = "v1", onBack = {}, onQualificationSubmitted = {})
    }
    @Test fun addVendor() = shoot("14_add_vendor") {
        AddVendorScreen(onDone = {}, onBack = {}, sampleLicenceBytes = { ByteArray(0) })
    }
}

/** A common budget phone in India, with the system font enlarged. */
@Config(application = Application::class, qualifiers = "w320dp-h3600dp-xhdpi", sdk = [34])
class SmallPhoneLargeFontScreenshotTest : ScreenshotBase("small_320dp_font130", 1.3f)

@Config(application = Application::class, qualifiers = "w360dp-h3600dp-xhdpi", sdk = [34])
class RegularPhoneScreenshotTest : ScreenshotBase("regular_360dp", 1.0f)
