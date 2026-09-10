import { NextResponse } from "next/server";
import type { FamilyAction } from "@/lib/types";

const acceptedActions: FamilyAction[] = ["contacted", "video_planned", "referral_requested"];

export async function POST(request: Request, context: { params: Promise<{ riskEventId: string }> }) {
  const { riskEventId } = await context.params;
  const body = (await request.json()) as { action?: FamilyAction };

  if (!body.action || !acceptedActions.includes(body.action)) {
    return NextResponse.json({ error: "不支持的关怀行动" }, { status: 400 });
  }

  return NextResponse.json({
    status: "recorded",
    action: body.action,
    riskEventId,
    recordedAt: new Date().toISOString()
  });
}
