# Keep Retrofit & Gson DTOs in com.sangam.app.network
-keep class com.sangam.app.network.** { *; }
-keepattributes Signature, InnerClasses, EnclosingMethod
-keepattributes RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations
-dontwarn okhttp3.**
-dontwarn okio.**

# Razorpay Checkout
-keep class com.razorpay.** { *; }
-dontwarn com.razorpay.**
