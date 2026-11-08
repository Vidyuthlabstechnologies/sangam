# Keep Retrofit & Gson DTOs in com.sangam.app.network
-keep class com.sangam.app.network.** { *; }
-keepattributes Signature, InnerClasses, EnclosingMethod
-keepattributes RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations
-dontwarn okhttp3.**
-dontwarn okio.**

# Razorpay Checkout
-keep class com.razorpay.** { *; }
-dontwarn com.razorpay.**

# Firebase & Play Services
-keep class com.google.firebase.** { *; }
-keep class com.google.android.gms.** { *; }
-dontwarn com.google.firebase.**
-dontwarn com.google.android.gms.**
