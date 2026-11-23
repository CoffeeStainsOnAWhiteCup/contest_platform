import { createBrowserRouter } from "react-router-dom";

import { RequireAuth } from "@/auth/guards";
import { AppShell } from "@/components/layout/AppShell";
import { CallbackPage } from "@/pages/CallbackPage";
import { ContestDetailPage } from "@/pages/ContestDetailPage";
import { ContestListPage } from "@/pages/ContestListPage";
import { GlobalRatingPage } from "@/pages/GlobalRatingPage";
import { HomePage } from "@/pages/HomePage";
import { LeaderboardPage } from "@/pages/LeaderboardPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ProblemPage } from "@/pages/ProblemPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { SubmissionDetailPage } from "@/pages/SubmissionDetailPage";
import { SubmissionsPage } from "@/pages/SubmissionsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "login", element: <LoginPage /> },
      { path: "register", element: <RegisterPage /> },
      { path: "auth/callback", element: <CallbackPage /> },
      { path: "contests", element: <ContestListPage /> },
      { path: "contests/:contestId", element: <ContestDetailPage /> },
      { path: "contests/:contestId/leaderboard", element: <LeaderboardPage /> },
      { path: "problems/:problemId", element: <ProblemPage /> },
      { path: "rating", element: <GlobalRatingPage /> },
      {
        element: <RequireAuth />,
        children: [
          { path: "submissions", element: <SubmissionsPage /> },
          { path: "submissions/:submissionId", element: <SubmissionDetailPage /> },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
