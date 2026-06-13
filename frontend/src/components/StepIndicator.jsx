export default function StepIndicator({ current, total = 3 }) {
  return (
    <div className="mb-6 flex justify-center">
      <span className="rounded-full border border-[#d7d9d2] bg-[#fbfbf8] px-4 py-1 text-sm font-semibold text-[#50534e]">
        {current} / {total}
      </span>
    </div>
  );
}
