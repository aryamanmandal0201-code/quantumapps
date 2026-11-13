import { useEffect, useState } from "react";
import { subscribeSlow } from "../api/client";

export default function WakeBanner() {
  const [slow, setSlow] = useState(false);
  useEffect(() => subscribeSlow(setSlow), []);
  if (!slow) return null;
  return (
    <div className="wake-banner" role="status">
      Still working. The free server sleeps when idle and can take up to a minute to wake up.
    </div>
  );
}
