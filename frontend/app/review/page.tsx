"use client";

import { EventReviewWorkspace } from "@/components/modules/EventReviewWorkspace";
import { motion } from "framer-motion";

export default function ReviewPage() {
  return <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.32 }}><EventReviewWorkspace /></motion.div>;
}
