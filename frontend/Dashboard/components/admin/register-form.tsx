"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";

export function RegisterEmployeeForm() {
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const [workLocation, setWorkLocation] = useState("");
  const [salary, setSalary] = useState({
    basicSalary: 0,
    conveyance: 0,
    medical: 0,
    special: 0,
    healthInsurance: 0,
    tds: 0
  });

  const handleSalaryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setSalary(prev => ({
      ...prev,
      [name]: parseFloat(value) || 0
    }));
  };

  const calculatedHra = salary.basicSalary * 0.4;
  const calculatedEpf = salary.basicSalary * 0.12;
  const resolvedConveyance = salary.conveyance > 0 ? salary.conveyance : salary.basicSalary * 0.05;
  const resolvedMedical = salary.medical > 0 ? salary.medical : salary.basicSalary * 0.05;
  const resolvedSpecial = salary.special > 0 ? salary.special : salary.basicSalary * 0.1;
  const grossSalary = salary.basicSalary + calculatedHra + resolvedConveyance + resolvedMedical + resolvedSpecial;
  const professionalTax = PROFESSIONAL_TAX_BY_LOCATION[workLocation] ?? 0;
  const totalDeductions = calculatedEpf + salary.healthInsurance + professionalTax + salary.tds;
  const netPay = grossSalary - totalDeductions;

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);

    const formData = new FormData(e.currentTarget);
    const data = Object.fromEntries(formData.entries()) as Record<string, FormDataEntryValue | boolean>;
    
    data.workLocation = workLocation;

    try {
      const token = localStorage.getItem("access_token");
      if (!token) {
        throw new Error("Admin session not found. Please log in again.");
      }

      const mcpApiUrl = process.env.NEXT_PUBLIC_MCP_API_URL || "http://localhost:8080";
      const response = await fetch(`${mcpApiUrl}/api/employees/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.error || "Failed to register employee");
      }

      toast.success("Employee registered successfully!");
      (e.target as HTMLFormElement).reset();
      setSalary({
        basicSalary: 0,
        conveyance: 0,
        medical: 0,
        special: 0,
        healthInsurance: 0,
        tds: 0
      });
      setWorkLocation("");
      router.push("/dashboard");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Registration failed. Please ensure the backend is running.";
      toast.error(message);
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto mt-10 bg-white dark:bg-zinc-900 border dark:border-zinc-800 rounded-xl shadow-sm overflow-hidden mb-20 text-zinc-900 dark:text-zinc-100">
      <div className="p-6 border-b dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50">
        <h2 className="text-xl font-semibold">Register New Employee</h2>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">Fill in the comprehensive employee details to synchronize with the payroll database.</p>
      </div>
      
      <form onSubmit={handleSubmit} className="p-6 space-y-8">
        {/* Personal & Job Details */}
        <div>
          <h3 className="text-lg font-medium mb-4 border-b border-zinc-200 dark:border-zinc-800 pb-2">Profile Details</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5"><label htmlFor="empno" className="text-sm font-medium">Employee No.</label><input id="empno" name="empno" required className="input-field w-full px-3 py-2 text-sm text-black border border-zinc-200 rounded-md bg-transparent" placeholder="EMP123" /></div>
            <div className="space-y-1.5"><label htmlFor="name" className="text-sm font-medium">Full Name</label><input id="name" name="name" required className="input-field w-full px-3 py-2 text-sm text-black border border-zinc-200 rounded-md bg-transparent" placeholder="John Doe" /></div>
            <div className="space-y-1.5"><label htmlFor="dept" className="text-sm font-medium">Department</label><input id="dept" name="dept" required className="input-field w-full px-3 py-2 text-sm text-black border border-zinc-200 rounded-md bg-transparent" placeholder="Engineering" /></div>
            <div className="space-y-1.5"><label htmlFor="designation" className="text-sm font-medium">Designation</label><input id="designation" name="designation" required className="input-field w-full px-3 py-2 text-sm text-black border border-zinc-200 rounded-md bg-transparent" placeholder="Software Engineer" /></div>
          </div>
          <div className="mt-4 space-y-1.5">
              <label htmlFor="workLocation" className="text-sm font-medium">Work Location</label>
            <div className="relative">
              <select
                id="workLocation"
                name="workLocation"
                required
                value={workLocation}
                onChange={(e) => setWorkLocation(e.target.value)}
                className="block w-full appearance-none rounded-md border border-zinc-300 bg-white px-3 py-2 pr-10 text-sm text-black shadow-sm outline-none transition focus:border-zinc-500 focus:ring-2 focus:ring-zinc-200"
                aria-describedby="workLocationHelp"
              >
                <option value="" disabled>Select work location</option>
                <option value="gurugram">Gurugram</option>
                <option value="bangalore">Bangalore</option>
                <option value="delhi">Delhi</option>
                <option value="noida">Noida</option>
                <option value="pune">Pune</option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-zinc-500">
                ▼
              </div>
            </div>
            <p id="workLocationHelp" className="text-xs text-zinc-500">
              Professional Tax is calculated automatically from the selected location.
            </p>
          </div>
        </div>

        {/* Bank Details */}
        <div>
          <h3 className="text-lg font-medium mb-4 border-b border-zinc-200 dark:border-zinc-800 pb-2">Bank Details</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5"><label className="text-sm font-medium">Bank Name</label><input name="bankName" required className="input-field w-full text-black px-3 py-2 text-sm border border-zinc-200 rounded-md bg-transparent" placeholder="Chase Bank" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Account No.</label><input name="accountNo" required className="input-field w-full text-black px-3 py-2 text-sm border border-zinc-200 rounded-md bg-transparent" placeholder="1234567890" /></div>
          </div>
        </div>

        {/* Salary Details */}
        <div>
          <h3 className="text-lg font-medium mb-4 border-b border-zinc-200 dark:border-zinc-800 pb-2">Salary Inputs</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="space-y-1.5"><label className="text-sm font-medium">Basic Salary</label><input name="basicSalary" type="number" step="0.01" required value={salary.basicSalary} onChange={handleSalaryChange} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-transparent" placeholder="0" /></div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Work Location</label>
              <div className="input-field w-full px-3 py-2 text-sm text-black border border-zinc-200 rounded-md bg-zinc-50 font-semibold">
                {workLocation ? WORK_LOCATION_LABELS[workLocation] : "Select work location above"}
              </div>
            </div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Conveyance</label><input name="conveyance" type="number" step="0.01" value={salary.conveyance} onChange={handleSalaryChange} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-transparent" placeholder="Optional, auto-calculated if empty" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Medical</label><input name="medical" type="number" step="0.01" value={salary.medical} onChange={handleSalaryChange} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-transparent" placeholder="Optional, auto-calculated if empty" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Special</label><input name="special" type="number" step="0.01" value={salary.special} onChange={handleSalaryChange} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-transparent" placeholder="Optional, auto-calculated if empty" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Health Insur.</label><input name="healthInsurance" type="number" step="0.01" required value={salary.healthInsurance} onChange={handleSalaryChange} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-transparent" placeholder="0" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">TDS</label><input name="tds" type="number" step="0.01" required value={salary.tds} onChange={handleSalaryChange} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-transparent" placeholder="0" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Auto HRA</label><input type="number" step="0.01" readOnly value={calculatedHra} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-zinc-50 cursor-not-allowed font-semibold" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Auto EPF</label><input type="number" step="0.01" readOnly value={calculatedEpf} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-zinc-50 cursor-not-allowed font-semibold" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Professional Tax</label><input type="number" step="0.01" readOnly value={professionalTax} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-zinc-50 cursor-not-allowed font-semibold" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Gross Salary</label><input type="number" step="0.01" readOnly value={grossSalary} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-zinc-50 cursor-not-allowed font-semibold" placeholder="Calculated automatically" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Total Ded.</label><input type="number" step="0.01" readOnly value={totalDeductions} className="input-field w-full text-black px-3 py-2 border border-zinc-200 rounded-md bg-zinc-50 cursor-not-allowed font-semibold" placeholder="Calculated automatically" /></div>
            <div className="space-y-1.5"><label className="text-sm font-medium">Net Pay</label><input type="number" step="0.01" readOnly value={netPay} className="input-field w-full px-3 py-2 border border-zinc-200 rounded-md bg-zinc-50 cursor-not-allowed font-semibold text-green-600" placeholder="Calculated automatically" /></div>
          </div>
        </div>



        <button 
          type="submit" 
          disabled={loading}
          className="w-full flex items-center justify-center py-3 px-4 mt-6 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-zinc-900 hover:bg-zinc-800 transition-colors"
        >
          {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : "Register Employee"}
        </button>
      </form>
    </div>
  );
}

const PROFESSIONAL_TAX_BY_LOCATION: Record<string, number> = {
  gurugram: 0,
  bangalore: 250,
  delhi: 200,
  noida: 150,
  pune: 200,
};

const WORK_LOCATION_LABELS: Record<string, string> = {
  gurugram: "Gurugram",
  bangalore: "Bangalore",
  delhi: "Delhi",
  noida: "Noida",
  pune: "Pune",
};
