plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "farm.kisamore.battle"
    compileSdk = 36

    defaultConfig {
        applicationId = "farm.kisamore.battle"
        minSdk = 26
        targetSdk = 36
        versionCode = 12
        versionName = "0.4.4"
    }

    val uploadStoreFile = System.getenv("KISAMORE_UPLOAD_STORE_FILE")
    val uploadStorePassword = System.getenv("KISAMORE_UPLOAD_STORE_PASSWORD")
    val uploadKeyAlias = System.getenv("KISAMORE_UPLOAD_KEY_ALIAS")
    val uploadKeyPassword = System.getenv("KISAMORE_UPLOAD_KEY_PASSWORD")

    signingConfigs {
        create("release") {
            if (
                !uploadStoreFile.isNullOrBlank() &&
                !uploadStorePassword.isNullOrBlank() &&
                !uploadKeyAlias.isNullOrBlank() &&
                !uploadKeyPassword.isNullOrBlank()
            ) {
                storeFile = file(uploadStoreFile)
                storePassword = uploadStorePassword
                keyAlias = uploadKeyAlias
                keyPassword = uploadKeyPassword
            }
        }
    }

    buildTypes {
        getByName("release") {
            isMinifyEnabled = false
            if (!uploadStoreFile.isNullOrBlank()) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
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
