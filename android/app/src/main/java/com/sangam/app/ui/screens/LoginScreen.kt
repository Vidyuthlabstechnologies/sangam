package com.sangam.app.ui.screens

import com.sangam.app.ui.components.str
import com.sangam.app.ui.components.LanguageDialog
import com.sangam.app.ui.components.TertiaryButton
import androidx.compose.material.icons.filled.Translate

import com.sangam.app.ui.components.SecondaryButton
import com.sangam.app.ui.components.PrimaryButton
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.common.api.ApiException
import com.google.android.gms.common.api.CommonStatusCodes
import com.google.android.gms.auth.api.signin.GoogleSignInStatusCodes
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import com.sangam.app.R
import com.sangam.app.network.FirebaseSession
import com.sangam.app.network.RealtimeClient
import com.sangam.app.ui.components.LegalFooter
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(onLoginSuccess: (isNewUser: Boolean) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val scrollState = rememberScrollState()

    var isLogin by remember { mutableStateOf(true) }
    var name by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var isPasswordFocused by remember { mutableStateOf(false) }
    var showPassword by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var info by remember { mutableStateOf<String?>(null) }

    fun finishSignIn(result: FirebaseSession.Result, provider: String) {
        syncFirestoreProfile(result.actorId, result.email.orEmpty(), result.name, provider)
        RealtimeClient.start()
        onLoginSuccess(result.isNewUser)
    }

    fun submit() {
        val cleanEmail = email.trim()
        val cleanName = name.trim()
        error = null
        info = null
        when {
            cleanEmail.isEmpty() || password.isEmpty() -> {
                error = str(R.string.please_enter_email_and_password)
                return
            }
            !android.util.Patterns.EMAIL_ADDRESS.matcher(cleanEmail).matches() -> {
                error = str(R.string.enter_a_valid_email_address)
                return
            }
            !isLogin && cleanName.isEmpty() -> {
                error = str(R.string.please_enter_your_name)
                return
            }
            !isLogin && password.length < 8 -> {
                error = str(R.string.use_at_least_8_characters_for)
                return
            }
        }
        loading = true
        scope.launch {
            try {
                val result = if (isLogin) {
                    FirebaseSession.signInWithEmail(cleanEmail, password)
                } else {
                    FirebaseSession.signUpWithEmail(cleanName, cleanEmail, password)
                }
                finishSignIn(result, "password")
            } catch (e: FirebaseSession.VerificationPending) {
                // Show the sign-in form so the user can sign in after tapping the link.
                isLogin = true
                password = ""
                error = e.message
            } catch (e: Exception) {
                error = e.message ?: str(R.string.sign_in_failed_please_try_again)
            } finally {
                loading = false
            }
        }
    }

    // Google Sign-In asks for an ID token that Firebase exchanges for a session.
    val googleSignInClient = remember {
        FirebaseSession.googleSignInOptions(context)?.let { GoogleSignIn.getClient(context, it) }
    }

    val googleLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val account = try {
            GoogleSignIn.getSignedInAccountFromIntent(result.data).getResult(ApiException::class.java)
        } catch (e: ApiException) {
            error = when (e.statusCode) {
                GoogleSignInStatusCodes.SIGN_IN_CANCELLED -> null
                CommonStatusCodes.NETWORK_ERROR -> str(R.string.no_internet_connection_check_your_network)
                CommonStatusCodes.DEVELOPER_ERROR ->
                    str(R.string.google_sign_in_is_not_set)
                else -> str(R.string.google_sign_in_did_not_complete, e.statusCode)
            }
            return@rememberLauncherForActivityResult
        }
        val idToken = account?.idToken
        if (idToken.isNullOrBlank()) {
            error = str(R.string.google_did_not_return_a_sign)
            return@rememberLauncherForActivityResult
        }
        scope.launch {
            loading = true
            error = null
            try {
                finishSignIn(FirebaseSession.signInWithGoogle(idToken), "google")
            } catch (e: Exception) {
                googleSignInClient?.signOut()
                error = e.message ?: str(R.string.google_sign_in_failed_please_try)
            } finally {
                loading = false
            }
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
                .verticalScroll(scrollState)
                .padding(horizontal = 24.dp, vertical = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            // Language comes first: someone who cannot read English must be able to switch before anything else.
            var showLanguages by remember { mutableStateOf(false) }
            Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterEnd) {
                TertiaryButton(onClick = { showLanguages = true }) {
                    Icon(Icons.Default.Translate, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(str(R.string.app_language))
                }
            }
            if (showLanguages) LanguageDialog(onDismiss = { showLanguages = false })
            Spacer(modifier = Modifier.height(8.dp))

            Text(
                str(R.string.sangamitra),
                style = MaterialTheme.typography.displayLarge,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold,
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                str(R.string.deploy_autonomous_voice_agents_in_seconds),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
            Spacer(modifier = Modifier.height(12.dp))

            // Witty Duolingo-style Mascot Speech Bubble (Clean White Theme)
            Surface(
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.3f)),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp)
            ) {
                Text(
                    text = if (isPasswordFocused) {
                        str(R.string.psst_enter_your_master_password_i)
                    } else {
                        str(R.string.namaste_ready, if (name.isNotBlank()) name else str(R.string.boss))
                    },
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.onSurface,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // 100% Transparent Mascot (No background box!)
            Image(
                painter = painterResource(
                    id = if (isPasswordFocused) R.drawable.mascot_kite_peekaboo else R.drawable.mascot_kite_idle
                ),
                contentDescription = null,
                modifier = Modifier
                    .size(120.dp)
                    .padding(bottom = 4.dp),
                contentScale = ContentScale.Fit
            )

            Spacer(modifier = Modifier.height(12.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            ) {
                Column(modifier = Modifier.padding(20.dp)) {

                    // Google Sign-In Button
                    SecondaryButton(
                        onClick = {
                            error = null
                            info = null
                            val client = googleSignInClient
                            if (client == null) {
                                error = str(R.string.google_sign_in_is_not_set)
                            } else {
                                // Start from a clean slate so the account picker always shows.
                                client.signOut().addOnCompleteListener {
                                    googleLauncher.launch(client.signInIntent)
                                }
                            }
                        },
                        // heightIn, not height: a fixed 48dp clips the label at large font sizes.
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                        enabled = !loading,
                        colors = ButtonDefaults.outlinedButtonColors(
                            containerColor = MaterialTheme.colorScheme.surface,
                        ),
                    ) {
                        Image(
                            painter = painterResource(R.drawable.ic_google_logo),
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            str(R.string.continue_with_google),
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    // Divider with text
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        HorizontalDivider(modifier = Modifier.weight(1f))
                        Text(
                            str(R.string.or_continue_with_email),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(horizontal = 8.dp),
                        )
                        HorizontalDivider(modifier = Modifier.weight(1f))
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    if (!isLogin) {
                        OutlinedTextField(
                            value = name,
                            onValueChange = { name = it },
                            label = { Text(str(R.string.full_name)) },
                            leadingIcon = { Icon(Icons.Default.Person, contentDescription = null) },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(
                                capitalization = KeyboardCapitalization.Words,
                                imeAction = ImeAction.Next,
                            ),
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                    }

                    OutlinedTextField(
                        value = email,
                        onValueChange = { email = it },
                        label = { Text(str(R.string.email)) },
                        leadingIcon = { Icon(Icons.Default.Email, contentDescription = null) },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Email,
                            imeAction = ImeAction.Next,
                        ),
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    OutlinedTextField(
                        value = password,
                        onValueChange = { password = it },
                        label = { Text(str(R.string.password)) },
                        leadingIcon = { Icon(Icons.Default.Lock, contentDescription = null) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .onFocusChanged { isPasswordFocused = it.isFocused },
                        singleLine = true,
                        visualTransformation = if (showPassword) VisualTransformation.None else PasswordVisualTransformation(),
                        trailingIcon = {
                            IconButton(onClick = { showPassword = !showPassword }) {
                                Icon(
                                    if (showPassword) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                                    contentDescription = if (showPassword) str(R.string.hide_password) else str(R.string.show_password),
                                )
                            }
                        },
                        supportingText = if (!isLogin) {
                            { Text(str(R.string.at_least_8_characters)) }
                        } else null,
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Password,
                            imeAction = ImeAction.Done,
                        ),
                        keyboardActions = KeyboardActions(onDone = { if (!loading) submit() }),
                    )

                    val displayError = error
                    if (displayError != null) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = displayError,
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                            textAlign = TextAlign.Center,
                            modifier = Modifier
                                .fillMaxWidth()
                                .semantics { liveRegion = LiveRegionMode.Assertive },
                        )
                    }
                    val displayInfo = info
                    if (displayInfo != null && displayError == null) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = displayInfo,
                            color = MaterialTheme.colorScheme.primary,
                            style = MaterialTheme.typography.bodySmall,
                            textAlign = TextAlign.Center,
                            modifier = Modifier
                                .fillMaxWidth()
                                .semantics { liveRegion = LiveRegionMode.Assertive },
                        )
                    }
                    Spacer(modifier = Modifier.height(16.dp))

                    PrimaryButton(
                        onClick = { submit() },
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                        enabled = !loading,
                    ) {
                        if (loading) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(24.dp),
                                color = MaterialTheme.colorScheme.onPrimary,
                                strokeWidth = 2.dp,
                            )
                        } else {
                            Text(
                                if (isLogin) str(R.string.sign_in) else str(R.string.create_account),
                                style = MaterialTheme.typography.labelLarge,
                            )
                        }
                    }

                    if (isLogin) {
                        TextButton(
                            onClick = {
                                val cleanEmail = email.trim()
                                error = null
                                info = null
                                if (!android.util.Patterns.EMAIL_ADDRESS.matcher(cleanEmail).matches()) {
                                    error = str(R.string.enter_your_email_above_then_tap)
                                    return@TextButton
                                }
                                scope.launch {
                                    try {
                                        FirebaseSession.sendPasswordReset(cleanEmail)
                                        info = str(R.string.if_an_account_exists_for_a, cleanEmail)
                                    } catch (e: Exception) {
                                        error = e.message
                                    }
                                }
                            },
                            enabled = !loading,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(str(R.string.forgot_password), style = MaterialTheme.typography.bodySmall)
                        }
                    } else {
                        Spacer(modifier = Modifier.height(8.dp))
                    }

                    TextButton(
                        onClick = {
                            isLogin = !isLogin
                            error = null
                            info = null
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            if (isLogin) str(R.string.don_t_have_an_account_sign) else str(R.string.already_have_an_account_sign_in),
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))
            Text(
                str(R.string.by_continuing_you_agree_to_the),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
            LegalFooter()
        }
    }
}

private fun syncFirestoreProfile(actorId: String, email: String, name: String, provider: String) {
    val firebaseUser = try {
        FirebaseAuth.getInstance().currentUser
    } catch (_: Exception) {
        null
    } ?: return
    try {
        val userDoc = hashMapOf(
            "uid" to firebaseUser.uid,
            "actorId" to actorId,
            "email" to email,
            "name" to name,
            "authProvider" to provider,
            "lastLogin" to FieldValue.serverTimestamp(),
        )
        FirebaseFirestore.getInstance()
            .collection("users")
            .document(firebaseUser.uid)
            .set(userDoc, SetOptions.merge())
    } catch (_: Exception) {
    }
}
