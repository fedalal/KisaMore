plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "farm.kisamore.battle"
    compileSdk = 35

    defaultConfig {
        applicationId = "farm.kisamore.battle"
        minSdk = 26
        targetSdk = 35
        versionCode = 7
        versionName = "0.3.4"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}
