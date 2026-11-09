plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.gms.google-services")
}

android {
    namespace = "com.sangam.app"
    compileSdk = 35
    ndkVersion = "27.1.12297006"

    defaultConfig {
        applicationId = "com.sangam.app"
        minSdk = 26
        targetSdk = 35
        // CI passes VERSION_CODE (it must rise with every Play upload) and VERSION_NAME.
        versionCode = ((project.findProperty("VERSION_CODE") as String?) ?: System.getenv("VERSION_CODE"))
            ?.toIntOrNull() ?: 100
        versionName = (project.findProperty("VERSION_NAME") as String?) ?: System.getenv("VERSION_NAME") ?: "1.0.0"

        fun buildConfigString(value: String): String {
            val escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
            return "\"$escaped\""
        }
        val zitadelIssuer = (project.findProperty("ZITADEL_ISSUER") as String?)
            ?: System.getenv("ZITADEL_ISSUER")
            ?: ""
        val zitadelClientId = (project.findProperty("ZITADEL_CLIENT_ID") as String?)
            ?: System.getenv("ZITADEL_CLIENT_ID")
            ?: ""
        buildConfigField("String", "ZITADEL_ISSUER", buildConfigString(zitadelIssuer))
        buildConfigField("String", "ZITADEL_CLIENT_ID", buildConfigString(zitadelClientId))
        // Optional fallback for Google Sign-In. Normally read from
        // default_web_client_id, which google-services.json provides once
        // Google is enabled as a Firebase Authentication provider.
        val googleWebClientId = (project.findProperty("GOOGLE_WEB_CLIENT_ID") as String?)
            ?: System.getenv("GOOGLE_WEB_CLIENT_ID")
            ?: ""
        buildConfigField("String", "GOOGLE_WEB_CLIENT_ID", buildConfigString(googleWebClientId))

        // RevenueCat public Android SDK key (goog_...). It is a public key, safe
        // in the app. Empty disables in-app purchases instead of crashing.
        val revenueCatKey = (project.findProperty("REVENUECAT_ANDROID_KEY") as String?)
            ?: System.getenv("REVENUECAT_ANDROID_KEY")
            ?: ""
        buildConfigField("String", "REVENUECAT_ANDROID_KEY", buildConfigString(revenueCatKey))

        // Public legal pages linked from the login and settings screens. Empty
        // falls back to the privacy page the backend serves.
        fun urlSetting(name: String) = (project.findProperty(name) as String?) ?: System.getenv(name) ?: ""
        buildConfigField("String", "PRIVACY_POLICY_URL", buildConfigString(urlSetting("PRIVACY_POLICY_URL")))
        buildConfigField("String", "TERMS_URL", buildConfigString(urlSetting("TERMS_URL")))
        buildConfigField("String", "ACCOUNT_DELETION_URL", buildConfigString(urlSetting("ACCOUNT_DELETION_URL")))
        manifestPlaceholders["appAuthRedirectScheme"] = "com.sangam.app"
    }

    val releaseStorePassword = (project.findProperty("SANGAM_KEYSTORE_PASSWORD") as String?)
        ?: System.getenv("SANGAM_KEYSTORE_PASSWORD")
    val releaseKeyPassword = (project.findProperty("SANGAM_KEY_PASSWORD") as String?)
        ?: System.getenv("SANGAM_KEY_PASSWORD")
    val releaseKeyAlias = (project.findProperty("SANGAM_KEY_ALIAS") as String?)
        ?: System.getenv("SANGAM_KEY_ALIAS")
        ?: "sangamitra"
    val releaseTaskRequested = gradle.startParameter.taskNames.any { name ->
        name.contains("release", ignoreCase = true)
    }
    if (releaseTaskRequested && (releaseStorePassword.isNullOrBlank() || releaseKeyPassword.isNullOrBlank())) {
        throw GradleException(
            "Release signing requires SANGAM_KEYSTORE_PASSWORD and SANGAM_KEY_PASSWORD from the environment or Gradle properties. No password is stored in source."
        )
    }

    signingConfigs {
        create("release") {
            if (!releaseStorePassword.isNullOrBlank() && !releaseKeyPassword.isNullOrBlank()) {
                storeFile = file("sangamitra-release.jks")
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        debug {
            isDebuggable = true
            val debugApi = (project.findProperty("API_BASE_URL") as String?)
                ?: System.getenv("API_BASE_URL")
                ?: "http://10.0.2.2:8000"
            buildConfigField("String", "API_BASE_URL", "\"$debugApi\"")
        }
        release {
            isDebuggable = false
            isMinifyEnabled = true
            if (!releaseStorePassword.isNullOrBlank() && !releaseKeyPassword.isNullOrBlank()) {
                signingConfig = signingConfigs.getByName("release")
            }
            val configuredApi = (project.findProperty("API_BASE_URL") as String?) ?: System.getenv("API_BASE_URL")
            val releaseApi = when {
                configuredApi.isNullOrBlank() -> "https://api.unconfigured.invalid"
                configuredApi.startsWith("https://") -> configuredApi
                releaseTaskRequested -> throw GradleException(
                    "Release API_BASE_URL must be https. Refusing a cleartext default."
                )
                else -> "https://api.unconfigured.invalid"
            }
            buildConfigField("String", "API_BASE_URL", "\"$releaseApi\"")
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    packaging {
        jniLibs {
            useLegacyPackaging = true
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    // Compose BOM
    val composeBom = platform("androidx.compose:compose-bom:2024.11.00")
    implementation(composeBom)

    // Material 3 Expressive
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material3:material3-window-size-class")
    implementation("androidx.compose.material:material-icons-extended")

    // Compose UI
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.animation:animation")

    // Navigation
    implementation("androidx.navigation:navigation-compose:2.8.4")

    // Lifecycle
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")

    // Activity
    implementation("androidx.activity:activity-compose:1.9.3")

    // Networking
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    // Firebase
    implementation(platform("com.google.firebase:firebase-bom:33.6.0"))
    implementation("com.google.firebase:firebase-messaging-ktx")
    implementation("com.google.firebase:firebase-auth-ktx")
    implementation("com.google.firebase:firebase-firestore-ktx")

    // Google Play Services Auth
    implementation("com.google.android.gms:play-services-auth:21.2.0")

    // Sarvam Voice SDK (for speech-to-text)
    // implementation("ai.sarvam:sarvam-android:1.0.0")

    // Google Play Billing through RevenueCat (Billing Library 8)
    implementation("com.revenuecat.purchases:purchases:9.29.1")

    // Razorpay (web and non-Play builds only; Play builds sell through Google Play Billing)
    implementation("com.razorpay:checkout:1.6.41")

    // Room
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")

    // WorkManager
    implementation("androidx.work:work-runtime-ktx:2.10.0")

    // Accompanist
    implementation("com.google.accompanist:accompanist-systemuicontroller:0.36.0")

    // Core
    implementation("androidx.core:core-ktx:1.15.0")

    // Zitadel authorization code + PKCE in Custom Tabs. No client secret.
    implementation("net.openid:appauth:0.11.1")
    implementation("androidx.browser:browser:1.8.0")

    // Encrypted token store. EncryptedSharedPreferences is deprecated; the call sites
    // read the JWT synchronously from an OkHttp interceptor, so DataStore would need
    // a larger async rewrite. This keeps tokens out of plaintext SharedPreferences.
    implementation("androidx.security:security-crypto:1.1.0-alpha06")

    // Debug
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
