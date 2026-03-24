import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { apiClient } from "../api/client";
import { Key } from "lucide-react";

export default function ChangePasswordScreen() {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }

    if (newPassword.length < 6) {
      setError("New password must be at least 6 characters long.");
      return;
    }

    setIsLoading(true);
    try {
      // The API endpoint utilizes JSON body since it uses a Pydantic Model (ChangePasswordRequest)
      await apiClient.post("/admin/change-password", {
        old_password: oldPassword,
        new_password: newPassword
      });
      setSuccess("Password successfully changed!");
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to change password. Ensure your original credentials are correct.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-xl mx-auto mt-12 w-full">
      <div className="flex items-center gap-3">
        <div className="bg-primary/20 p-2 rounded-lg">
          <Key className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Security</h2>
          <p className="text-muted-foreground">Manage your account credentials.</p>
          <p className="text-xs text-muted-foreground">
            Collection: <span className="font-mono">admin_users</span> | Key: <span className="font-mono">username</span>
          </p>
        </div>
      </div>
      
      <Card>
        <form onSubmit={handleSubmit}>
          <CardHeader>
            <CardTitle>Change Password</CardTitle>
            <CardDescription>Update your administrator password here. Make sure to choose a strong one.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="old_password">Current Password</Label>
              <Input
                id="old_password"
                type="password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new_password">New Password</Label>
              <Input
                id="new_password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm_password">Confirm New Password</Label>
              <Input
                id="confirm_password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </div>
            {error && <p className="text-sm font-medium text-destructive">{error}</p>}
            {success && <p className="text-sm font-medium text-green-600 dark:text-green-400">{success}</p>}
          </CardContent>
          <CardFooter>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? "Updating..." : "Update Password"}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
