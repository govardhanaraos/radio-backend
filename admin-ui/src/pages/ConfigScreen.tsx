import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { apiClient } from "../api/client";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const configSchema = z.object({
  languages_enabled: z.boolean(),
  languages: z.array(
    z.object({
      label: z.string().min(1, "Label is required"),
      value: z.string().min(1, "Value is required"),
    })
  ),
  content_types_enabled: z.boolean(),
  content_types: z.array(
    z.object({
      label: z.string(),
      value: z.string(),
      icon: z.string(),
    })
  ),
  browse_by_album_enabled: z.boolean(),
  album_entries: z.array(
    z.object({
      label: z.string(),
      lang: z.string(),
      base_url: z.string().url(),
      icon: z.string(),
      color_a: z.string(),
      color_b: z.string(),
      enabled: z.boolean(),
    })
  ),
  old_archive_enabled: z.boolean(),
});

type ConfigValues = z.infer<typeof configSchema>;

const appUpdateSchema = z.object({
  app_update_enabled: z.preprocess((v) => {
    if (typeof v === "string") {
      const s = v.trim().toLowerCase();
      return s === "true" || s === "1" || s === "yes";
    }
    return v;
  }, z.boolean()),
  app_update_version: z.string().min(1, "Version is required"),
  app_update_url: z.string().min(1, "URL is required").url("Invalid URL"),
});

type AppUpdateValues = z.infer<typeof appUpdateSchema>;

export default function ConfigScreen() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Fetch the data
  const { data, isLoading, error } = useQuery({
    queryKey: ["appconfig", "download_screen"],
    queryFn: async () => {
      const res = await apiClient.get<ConfigValues>("/appconfig/download-screen");
      return res.data;
    },
  });

  const {
    data: appUpdateData,
    isLoading: isAppUpdateLoading,
    error: appUpdateError,
  } = useQuery({
    queryKey: ["appconfig", "availableupdate"],
    queryFn: async () => {
      const res = await apiClient.get<{
        status: string;
        config: Record<string, unknown>;
      }>("/appconfig/availableupdate");

      return res.data.config;
    },
  });

  // Setup form
  const form = useForm<ConfigValues>({
    resolver: zodResolver(configSchema),
    defaultValues: data || {
      languages_enabled: true,
      languages: [],
      content_types_enabled: true,
      content_types: [],
      browse_by_album_enabled: true,
      album_entries: [],
      old_archive_enabled: true,
    },
  });

  const appUpdateForm = useForm<AppUpdateValues>({
    resolver: zodResolver(appUpdateSchema) as any,
    defaultValues: {
      app_update_enabled:
        typeof (appUpdateData as any)?.app_update_enabled !== "undefined"
          ? (appUpdateData as any)?.app_update_enabled
          : false,
      app_update_version: (appUpdateData as any)?.app_update_version ?? "",
      app_update_url: (appUpdateData as any)?.app_update_url ?? "",
    },
  });

  // Reset form when data arrives
  import("react").then((React) => {
    React.useEffect(() => {
      if (data) {
        form.reset(data);
      }
    }, [data, form]);

    React.useEffect(() => {
      if (!appUpdateData) return;
      appUpdateForm.reset({
        app_update_enabled: (appUpdateData as any)?.app_update_enabled ?? false,
        app_update_version: (appUpdateData as any)?.app_update_version ?? "",
        app_update_url: (appUpdateData as any)?.app_update_url ?? "",
      });
    }, [appUpdateData, appUpdateForm]);
  });

  const { fields: languageFields, append: appendLang, remove: removeLang } = useFieldArray({
    name: "languages",
    control: form.control,
  });

  const { fields: albumFields, append: appendAlbum, remove: removeAlbum } = useFieldArray({
    name: "album_entries",
    control: form.control,
  });

  // Mutation to save data
  const mutation = useMutation({
    mutationFn: async (values: ConfigValues) => {
      const res = await apiClient.put("/appconfig/download-screen", values);
      return res.data;
    },
    onSuccess: () => {
      toast({
        title: "Success",
        description: "Configuration saved successfully.",
      });
      queryClient.invalidateQueries({ queryKey: ["appconfig", "download_screen"] });
    },
    onError: (err) => {
      toast({
        title: "Error",
        description: "Failed to save configuration: " + err.message,
        variant: "destructive",
      });
    },
  });

  function onSubmit(values: ConfigValues) {
    mutation.mutate(values);
  }

  const updateMutation = useMutation({
    mutationFn: async (values: AppUpdateValues) => {
      const res = await apiClient.put("/appconfig/availableupdate", values);
      return res.data;
    },
    onSuccess: () => {
      toast({
        title: "Success",
        description: "App update configuration saved successfully.",
      });
      queryClient.invalidateQueries({ queryKey: ["appconfig", "availableupdate"] });
    },
    onError: (err) => {
      toast({
        title: "Error",
        description: "Failed to save app update configuration: " + err.message,
        variant: "destructive",
      });
    },
  });

  function onSubmitAppUpdate(values: AppUpdateValues) {
    updateMutation.mutate(values);
  }

  if (isLoading || isAppUpdateLoading) {
    return (
      <div className="flex flex-col gap-4 w-full h-[60vh] items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        <p className="text-muted-foreground animate-pulse">Connecting to backend services...</p>
      </div>
    );
  }
  if (error || appUpdateError) {
    return (
      <div className="p-8 text-destructive">
        Failed to fetch config data. Please ensure the backend is running.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 w-full max-w-5xl mx-auto">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">App Configuration</h2>
        <p className="text-muted-foreground">
          Manage the mobile app's download screen structure, languages, and themes.
        </p>
        <p className="text-xs text-muted-foreground">
          Collection: <span className="font-mono">app_parameters</span> | Key: <span className="font-mono">config_key=download_screen</span>
        </p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
          <Tabs defaultValue="general" className="w-full">
            <TabsList className="mb-4">
              <TabsTrigger value="general">General</TabsTrigger>
              <TabsTrigger value="languages">Languages</TabsTrigger>
              <TabsTrigger value="albums">Albums Grid</TabsTrigger>
            </TabsList>

            {/* General Tab */}
            <TabsContent value="general" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Global Toggles</CardTitle>
                  <CardDescription>Enable or disable major sections on the download screen.</CardDescription>
                  <p className="text-xs text-muted-foreground">
                    Collection: <span className="font-mono">app_parameters</span> | Key: <span className="font-mono">config_key=download_screen</span>
                  </p>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="languages_enabled"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                        <div className="space-y-0.5">
                          <FormLabel className="text-base">Languages Enabled</FormLabel>
                          <FormDescription>Show language filters on the app.</FormDescription>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="content_types_enabled"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                        <div className="space-y-0.5">
                          <FormLabel className="text-base">Content Types Enabled</FormLabel>
                          <FormDescription>Show tiles for Songs, Movies, etc.</FormDescription>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="old_archive_enabled"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                        <div className="space-y-0.5">
                          <FormLabel className="text-base">Old MP3 Archive Enabled</FormLabel>
                          <FormDescription>Show the legacy MP3 archive button.</FormDescription>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            {/* Languages Tab */}
            <TabsContent value="languages" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Configured Languages</CardTitle>
                  <CardDescription>Add or remove supported languages for filtering.</CardDescription>
                  <p className="text-xs text-muted-foreground">
                    Collection: <span className="font-mono">app_parameters</span> | Key: <span className="font-mono">config_key=download_screen</span>
                  </p>
                </CardHeader>
                <CardContent className="space-y-4">
                  {languageFields.map((field, index) => (
                    <div key={field.id} className="flex gap-4 items-end">
                      <FormField
                        control={form.control}
                        name={`languages.${index}.label`}
                        render={({ field }) => (
                          <FormItem className="flex-1">
                            <FormLabel>Label</FormLabel>
                            <FormControl>
                              <Input {...field} placeholder="e.g. Telugu" />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`languages.${index}.value`}
                        render={({ field }) => (
                          <FormItem className="flex-1">
                            <FormLabel>Value</FormLabel>
                            <FormControl>
                              <Input {...field} placeholder="e.g. telugu" />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <Button variant="destructive" type="button" onClick={() => removeLang(index)}>
                        Remove
                      </Button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => appendLang({ label: "", value: "" })}
                  >
                    Add Language
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Albums Tab */}
            <TabsContent value="albums" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Browse By Album Grid</CardTitle>
                  <CardDescription>Configure language cards their gradient colors, and base URLs.</CardDescription>
                  <p className="text-xs text-muted-foreground">
                    Collection: <span className="font-mono">app_parameters</span> | Key: <span className="font-mono">config_key=download_screen</span>
                  </p>
                  <FormField
                    control={form.control}
                    name="browse_by_album_enabled"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4 mt-2">
                        <div className="space-y-0.5">
                          <FormLabel className="text-base">Browse Grid Enabled</FormLabel>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                </CardHeader>
                <CardContent className="space-y-8">
                  {albumFields.map((field, index) => (
                    <div key={field.id} className="space-y-4 border p-4 rounded-lg bg-card">
                      <div className="flex justify-between items-center">
                        <h4 className="font-semibold">Card {index + 1}</h4>
                        <Button variant="destructive" size="sm" type="button" onClick={() => removeAlbum(index)}>
                          Remove Card
                        </Button>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <FormField
                          control={form.control}
                          name={`album_entries.${index}.label`}
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Label</FormLabel>
                              <FormControl><Input {...field} /></FormControl>
                            </FormItem>
                          )}
                        />
                         <FormField
                          control={form.control}
                          name={`album_entries.${index}.lang`}
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>API Key (lang)</FormLabel>
                              <FormControl><Input {...field} /></FormControl>
                            </FormItem>
                          )}
                        />
                         <FormField
                          control={form.control}
                          name={`album_entries.${index}.base_url`}
                          render={({ field }) => (
                            <FormItem className="col-span-2">
                              <FormLabel>Base URL</FormLabel>
                              <FormControl><Input {...field} /></FormControl>
                            </FormItem>
                          )}
                        />
                         <FormField
                          control={form.control}
                          name={`album_entries.${index}.color_a`}
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Gradient Start</FormLabel>
                              <FormControl>
                                <div className="flex gap-2">
                                  <Input type="color" {...field} className="w-12 p-1" />
                                  <Input {...field} />
                                </div>
                              </FormControl>
                            </FormItem>
                          )}
                        />
                         <FormField
                          control={form.control}
                          name={`album_entries.${index}.color_b`}
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Gradient End</FormLabel>
                              <FormControl>
                                <div className="flex gap-2">
                                  <Input type="color" {...field} className="w-12 p-1" />
                                  <Input {...field} />
                                </div>
                              </FormControl>
                            </FormItem>
                          )}
                        />
                        <FormField
                            control={form.control}
                            name={`album_entries.${index}.enabled`}
                            render={({ field }) => (
                              <FormItem className="flex items-center gap-2 mt-8">
                                <FormControl>
                                  <Switch checked={field.value} onCheckedChange={field.onChange} />
                                </FormControl>
                                <FormLabel>Card Active</FormLabel>
                              </FormItem>
                            )}
                          />
                      </div>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => appendAlbum({ label: "", lang: "", base_url: "https://", icon: "library_music", color_a: "#000000", color_b: "#aaaaaa", enabled: true })}
                  >
                    Add Album Card
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          <Button type="submit" size="lg" disabled={mutation.isPending}>
            {mutation.isPending ? "Saving..." : "Save Configuration"}
          </Button>
        </form>
      </Form>

      <div className="space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-2xl font-bold tracking-tight">App Update</h3>
            <p className="text-muted-foreground">
              Configure whether the app should show an update popup and which version/URL to use.
            </p>
          </div>
        </div>

        <Form {...appUpdateForm}>
          <form
            onSubmit={appUpdateForm.handleSubmit(onSubmitAppUpdate)}
            className="space-y-6 rounded-lg"
          >
            <Card>
              <CardHeader>
                <CardTitle>Update Popup Configuration</CardTitle>
                <CardDescription>Values come from `app_parameters` (parameter_code: app_update_*)</CardDescription>
                <p className="text-xs text-muted-foreground">
                  Collection: <span className="font-mono">app_parameters</span> | Key: <span className="font-mono">parameter_code=app_update_enabled/app_update_version/app_update_url</span>
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                <FormField
                  control={appUpdateForm.control}
                  name="app_update_enabled"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                      <div className="space-y-0.5">
                        <FormLabel className="text-base">Enable App Update</FormLabel>
                        <FormDescription>Show update popup when the app checks version.</FormDescription>
                      </div>
                      <FormControl>
                        <Switch checked={field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                    </FormItem>
                  )}
                />

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={appUpdateForm.control}
                    name="app_update_version"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Target Version</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="e.g. 1.0.5" />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={appUpdateForm.control}
                    name="app_update_url"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Update URL</FormLabel>
                        <FormControl>
                          <Input {...field} type="url" placeholder="https://play.google.com/..." />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <Button type="submit" size="lg" disabled={updateMutation.isPending}>
                  {updateMutation.isPending ? "Saving..." : "Save App Update"}
                </Button>
              </CardContent>
            </Card>
          </form>
        </Form>
      </div>
    </div>
  );
}
