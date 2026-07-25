package com.sangam.app.ui.screens

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.razorpay.Checkout
import com.sangam.app.network.ApiClient
import com.sangam.app.network.InitiatePaymentRequest
import com.sangam.app.network.VerifyPaymentRequest
import kotlinx.coroutines.launch
import org.json.JSONObject

object RazorpayState {
    var pendingListener: ((razorpayPaymentId: String, razorpayOrderId: String) -> Unit)? = null
    var pendingErrorListener: ((message: String) -> Unit)? = null
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PaymentScreen(
    workflowId: String,
    workflowName: String,
    onBack: () -> Unit = {},
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var amountText by remember { mutableStateOf("") }
    var paymentStatus by remember { mutableStateOf<String?>(null) }
    var paymentId by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Payment") },
                navigationIcon = {
                    TextButton(onClick = onBack) { Text("Back") }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                ),
            ) {
                Row(modifier = Modifier.padding(16.dp)) {
                    Column {
                        Text("Workflow", style = MaterialTheme.typography.labelMedium)
                        Text(workflowName, fontWeight = FontWeight.Bold)
                    }
                }
            }

            Spacer(modifier = Modifier.height(32.dp))

            if (paymentStatus != null) {
                val isSuccess = paymentStatus == "captured"
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = if (isSuccess) MaterialTheme.colorScheme.primaryContainer
                                        else MaterialTheme.colorScheme.errorContainer,
                    ),
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(32.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(
                            if (isSuccess) "Payment Successful" else "Payment Failed",
                            style = MaterialTheme.typography.headlineSmall,
                        )
                        if (paymentId != null) {
                            Spacer(modifier = Modifier.height(8.dp))
                            Text("ID: $paymentId", style = MaterialTheme.typography.bodySmall)
                        }
                        Spacer(modifier = Modifier.height(24.dp))
                        Button(onClick = onBack) { Text("Done") }
                    }
                }
                return@Column
            }

            OutlinedTextField(
                value = amountText,
                onValueChange = { amountText = it.filter { c -> c.isDigit() || c == '.' } },
                label = { Text("Amount") },
                modifier = Modifier.fillMaxWidth(),
                prefix = { Text("₹ ") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                singleLine = true,
            )

            Spacer(modifier = Modifier.height(24.dp))

            Button(
                onClick = {
                    val amount = amountText.toDoubleOrNull()
                    if (amount == null || amount <= 0) return@Button
                    loading = true
                    scope.launch {
                        try {
                            val response = ApiClient.paymentApi.initiatePayment(
                                InitiatePaymentRequest(
                                    workflow_id = workflowId,
                                    amount = amount,
                                    currency = "INR",
                                    description = "Payment for $workflowName",
                                ),
                            )

                            RazorpayState.pendingListener = { razorpayPaymentId, razorpayOrderId ->
                                scope.launch {
                                    try {
                                        val verifyResult = ApiClient.paymentApi.verifyPayment(
                                            VerifyPaymentRequest(
                                                razorpay_order_id = razorpayOrderId,
                                                razorpay_payment_id = razorpayPaymentId,
                                                razorpay_signature = "$razorpayOrderId|$razorpayPaymentId",
                                            ),
                                        )
                                        paymentStatus = verifyResult.status
                                    } catch (e: Exception) {
                                        paymentStatus = "verify_error"
                                    }
                                }
                            }

                            RazorpayState.pendingErrorListener = { msg ->
                                paymentStatus = "cancelled"
                            }

                            val activity = context as? ComponentActivity
                            if (activity == null) {
                                paymentStatus = "error: not attached to activity"
                                return@launch
                            }

                            val checkout = Checkout()
                            checkout.setKeyID(response.razorpay_key_id)

                            val options = JSONObject().apply {
                                put("name", "Sangam")
                                put("description", "Payment for $workflowName")
                                put("order_id", response.razorpay_order_id)
                                put("currency", response.currency)
                                put("amount", (response.amount * 100).toLong())
                                put("theme.color", "#6750A4")
                            }

                            checkout.open(activity, options)
                        } catch (e: Exception) {
                            paymentStatus = "error: ${e.message}"
                        }
                        loading = false
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = !loading,
            ) {
                if (loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                    Spacer(Modifier.width(8.dp))
                }
                Text(if (loading) "Initializing..." else "Pay with Razorpay")
            }

            Spacer(modifier = Modifier.height(32.dp))

            Text(
                "Secured by Razorpay",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.align(Alignment.CenterHorizontally),
            )
        }
    }
}
