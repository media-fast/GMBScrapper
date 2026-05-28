import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { ResultsPage } from "./pages/ResultsPage";
import { BusinessDetailPage } from "./pages/BusinessDetailPage";

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<ResultsPage />} />
        <Route path="/business/:dedupKey" element={<BusinessDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
