import org.gradle.api.file.DuplicatesStrategy

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.fundshare.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.fundshare.app"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0-android"

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
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
    }

    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

chaquopy {
    defaultConfig {
        version = "3.12"
        // Windows: py -3.12；构建机需已安装对应 Python（Chaquopy 文档要求）
        buildPython("py", "-3.12")
        pip {
            install("requests")
        }
    }
}

tasks.register<Copy>("syncFundsharePython") {
    from(layout.projectDirectory.dir("../../fundshare"))
    into(layout.projectDirectory.dir("src/main/python/fundshare"))
    duplicatesStrategy = DuplicatesStrategy.INCLUDE
}

tasks.named("preBuild") {
    dependsOn("syncFundsharePython")
}

// Gradle 8：Chaquopy 的 merge*PythonSources 与 sync 写同一目录，需显式依赖
afterEvaluate {
    listOf("mergeDebugPythonSources", "mergeReleasePythonSources").forEach { taskName ->
        tasks.findByName(taskName)?.dependsOn("syncFundsharePython")
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.02.02"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.9.0")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
}
