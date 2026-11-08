plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.sangam.app"
    compileSdk = 35
    ndkVersion = "27.1.12297006"

    defaultConfig {
        applicationId = "com.sangam.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 100
        versionName = "1.0.0"
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

    // Sarvam Voice SDK (for speech-to-text)
    // implementation("ai.sarvam:sarvam-android:1.0.0")

    // Razorpay
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

    // Encrypted token store. EncryptedSharedPreferences is deprecated; the call sites
    // read the JWT synchronously from an OkHttp interceptor, so DataStore would need
    // a larger async rewrite. This keeps tokens out of plaintext SharedPreferences.
    implementation("androidx.security:security-crypto:1.1.0-alpha06")

    // Debug
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
