import { NextResponse } from "next/server";
import { mockFamilyToday } from "@/lib/mock-family-data";

export async function GET(_request: Request, context: { params: Promise<{ elderId: string }> }) {
  const { elderId } = await context.params;

  return NextResponse.json({
    ...mockFamilyToday,
    elder: {
      ...mockFamilyToday.elder,
      id: elderId
    }
  });
}
