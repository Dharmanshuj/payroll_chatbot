"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";

export function UpdateAttendanceForm() {
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  
  const [empId, setEmpId] = useState("");
  const [attendance, setAttendance] = useState({
    totalDays: 0,
    presentDays: 0,
    month: "",
    year: ""
  });

  const handleAttendanceChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setAttendance(prev => ({
      ...prev,
      [name]: name === "month" || name === "year" ? value : parseInt(value || "0", 10) || 0
    }));
  };

  const absentDays = Math.max(attendance.totalDays - attendance.presentDays, 0);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);

    const payload = {
      empno: empId,
      month: attendance.month,
      year: parseInt(attendance.year, 10),
      totalDays: attendance.totalDays,
      presentDays: attendance.presentDays,
      absentDays: absentDays
    };

    try {
      const token = localStorage.getItem("access_token");
      if (!token) {
        throw new Error("Admin session not found. Please log in again.");
      }

      const mcpApiUrl = process.env.NEXT_PUBLIC_MCP_API_URL || "http://localhost:8080";
      const response = await fetch(`${mcpApiUrl}/api/employees/attendance`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.error || "Failed to update employee attendance");
      }

      toast.success("Employee attendance updated successfully!");
      (e.target as HTMLFormElement).reset();
      
      setEmpId("");
      setAttendance({
        totalDays: 0,
        presentDays: 0,
        month: "",
        year: ""
      });
      router.push("/dashboard");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Update failed. Please ensure the backend is running.";
      toast.error(message);
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto mt-10 bg-white dark:bg-zinc-900 border dark:border-zinc-800 rounded-xl shadow-sm overflow-hidden mb-20 text-zinc-900 dark:text-zinc-100">
      <div className="p-6 border-b dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50">
        <h2 className="text-xl font-semibold">Update Employee Attendance</h2>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">Modify or log the attendance record for an existing employee for a particular month.</p>
      </div>
      
      <form onSubmit={handleSubmit} className="p-6 space-y-8">
        {/* Verification Details */}
        <div>
          <h3 className="text-lg font-medium mb-4 border-b border-zinc-200 dark:border-zinc-800 pb-2">Employee Identification</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="empId" className="text-sm font-medium">Employee No.</label>
              <input 
                id="empId" 
                name="empId" 
                required 
                value={empId}
                onChange={(e) => setEmpId(e.target.value)}
                className="input-field w-full px-3 py-2 text-sm text-black border border-zinc-200 rounded-md bg-transparent" 
                placeholder="EMP123" 
              />
            </div>
          </div>
        </div>

        {/* Attendance Details */}
        <div>
          <h3 className="text-lg font-medium mb-4 border-b border-zinc-200 dark:border-zinc-800 pb-2">Monthly Attendance Metrics</h3>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="space-y-1.5"><label className="text-sm font-medium">Total Days</label><input name="totalDays" type="number" required value={attendance.totalDays || ""} onChange={handleAttendanceChange} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-transparent" placeholder="30" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Present</label><input name="presentDays" type="number" required value={attendance.presentDays || ""} onChange={handleAttendanceChange} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-transparent" placeholder="28" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Absent</label><input type="number" readOnly value={absentDays} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-zinc-50 cursor-not-allowed font-semibold" placeholder="Calculated automatically" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Month</label><input name="month" type="number" min="1" max="12" required value={attendance.month} onChange={handleAttendanceChange} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-transparent" placeholder="10" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Year</label><input name="year" type="number" min="2000" max="2100" required value={attendance.year} onChange={handleAttendanceChange} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-transparent" placeholder="2023" /></div>
          </div>
        </div>

        <button 
          type="submit" 
          disabled={loading}
          className="w-full flex items-center justify-center py-3 px-4 mt-6 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-zinc-900 hover:bg-zinc-800 transition-colors"
        >
          {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : "Update Attendance"}
        </button>
      </form>
    </div>
  );
}
