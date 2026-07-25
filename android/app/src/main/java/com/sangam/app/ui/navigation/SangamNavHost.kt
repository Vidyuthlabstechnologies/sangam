package com.sangam.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.sangam.app.ui.screens.*

object Routes {
    const val LOGIN = "login"
    const val DASHBOARD = "dashboard"
    const val WORKFLOWS = "workflows"
    const val WORKFLOW_DETAIL = "workflows/{workflowId}"
    const val APPROVALS = "approvals"
    const val ACTORS = "actors"
    const val AI_ASSISTANT = "ai_assistant"
    const val VOICE_WORKFLOW = "voice_workflow"
    const val PAYMENT = "payment/{workflowId}/{workflowName}"

    fun workflowDetail(id: String) = "workflows/$id"
    fun payment(workflowId: String, workflowName: String) = "payment/$workflowId/$workflowName"
}

@Composable
fun SangamNavHost(
    navController: NavHostController,
    startDestination: String,
) {
    NavHost(navController = navController, startDestination = startDestination) {
        composable(Routes.LOGIN) {
            LoginScreen(
                onLoginSuccess = {
                    navController.navigate(Routes.DASHBOARD) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                },
            )
        }
        composable(Routes.DASHBOARD) {
            DashboardScreen(
                onNavigateToWorkflows = { navController.navigate(Routes.WORKFLOWS) },
                onNavigateToApprovals = { navController.navigate(Routes.APPROVALS) },
                onNavigateToActors = { navController.navigate(Routes.ACTORS) },
                onNavigateToAIAssistant = { navController.navigate(Routes.AI_ASSISTANT) },
                onNavigateToVoiceWorkflow = { navController.navigate(Routes.VOICE_WORKFLOW) },
            )
        }
        composable(Routes.WORKFLOWS) {
            WorkflowListScreen(
                onWorkflowClick = { id -> navController.navigate(Routes.workflowDetail(id)) },
                onVoiceCreate = { navController.navigate(Routes.VOICE_WORKFLOW) },
            )
        }
        composable(
            route = Routes.WORKFLOW_DETAIL,
            arguments = listOf(navArgument("workflowId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val workflowId = backStackEntry.arguments?.getString("workflowId") ?: return@composable
            WorkflowDetailScreen(
                workflowId = workflowId,
                onBack = { navController.popBackStack() },
                onPay = { wfId, wfName ->
                    navController.navigate(Routes.payment(wfId, wfName))
                },
            )
        }
        composable(Routes.APPROVALS) {
            ApprovalsScreen(
                onWorkflowClick = { id -> navController.navigate(Routes.workflowDetail(id)) },
            )
        }
        composable(Routes.ACTORS) {
            ActorsScreen()
        }
        composable(Routes.AI_ASSISTANT) {
            AIAssistantScreen(
                onBack = { navController.popBackStack() },
            )
        }
        composable(Routes.VOICE_WORKFLOW) {
            VoiceWorkflowScreen(
                onBack = { navController.popBackStack() },
                onWorkflowCreated = {
                    navController.navigate(Routes.WORKFLOWS) {
                        popUpTo(Routes.DASHBOARD)
                    }
                },
            )
        }
        composable(
            route = Routes.PAYMENT,
            arguments = listOf(
                navArgument("workflowId") { type = NavType.StringType },
                navArgument("workflowName") { type = NavType.StringType },
            ),
        ) { backStackEntry ->
            val workflowId = backStackEntry.arguments?.getString("workflowId") ?: return@composable
            val workflowName = backStackEntry.arguments?.getString("workflowName") ?: "Workflow"
            PaymentScreen(
                workflowId = workflowId,
                workflowName = workflowName,
                onBack = { navController.popBackStack() },
            )
        }
    }
}
