import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { TokenGate } from "./components/TokenGate";
import { Layout } from "./components/Layout";
import { Home } from "./pages/Home";
import { Connectors } from "./pages/Connectors";
import { ConnectorForm } from "./pages/ConnectorForm";

function Gated() {
  const { status } = useAuth();

  if (status === "checking") {
    return <div className="center-screen">Loading…</div>;
  }
  if (status === "unauthenticated") {
    return <TokenGate />;
  }

  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="connectors" element={<Connectors />} />
        <Route path="connectors/new" element={<ConnectorForm />} />
        <Route path="connectors/:id/edit" element={<ConnectorForm />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter basename="/ui">
      <AuthProvider>
        <Gated />
      </AuthProvider>
    </BrowserRouter>
  );
}
