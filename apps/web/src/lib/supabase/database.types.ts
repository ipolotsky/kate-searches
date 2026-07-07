export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  public: {
    Tables: {
      ai_usage: {
        Row: {
          cost_usd: number
          created_at: string
          id: string
          input_tokens: number | null
          model: string | null
          output_tokens: number | null
          pipeline_run_id: string | null
          request_id: string | null
          stage: string
          tenant_id: string
          user_id: string | null
        }
        Insert: {
          cost_usd?: number
          created_at?: string
          id?: string
          input_tokens?: number | null
          model?: string | null
          output_tokens?: number | null
          pipeline_run_id?: string | null
          request_id?: string | null
          stage: string
          tenant_id: string
          user_id?: string | null
        }
        Update: {
          cost_usd?: number
          created_at?: string
          id?: string
          input_tokens?: number | null
          model?: string | null
          output_tokens?: number | null
          pipeline_run_id?: string | null
          request_id?: string | null
          stage?: string
          tenant_id?: string
          user_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "ai_usage_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "ai_usage_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      article_sources: {
        Row: {
          article_id: string
          external_id: string | null
          first_seen_at: string
          id: string
          priority_at_seen: number | null
          source_id: string | null
          tenant_id: string
        }
        Insert: {
          article_id: string
          external_id?: string | null
          first_seen_at?: string
          id?: string
          priority_at_seen?: number | null
          source_id?: string | null
          tenant_id: string
        }
        Update: {
          article_id?: string
          external_id?: string | null
          first_seen_at?: string
          id?: string
          priority_at_seen?: number | null
          source_id?: string | null
          tenant_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "article_sources_article_id_fkey"
            columns: ["article_id"]
            isOneToOne: false
            referencedRelation: "articles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "article_sources_source_id_fkey"
            columns: ["source_id"]
            isOneToOne: false
            referencedRelation: "sources"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "article_sources_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      articles: {
        Row: {
          author: string | null
          body: string | null
          canonical_url: string
          content_hash: string | null
          created_at: string
          duplicate_of: string | null
          external_id: string | null
          fetched_at: string
          id: string
          language: string | null
          last_pipeline_run_id: string | null
          media: Json
          metadata: Json
          published_at: string | null
          relevance: Json | null
          relevance_score: number | null
          simhash: number | null
          source_id: string | null
          status: string
          summary: string | null
          tags: string[]
          tenant_id: string
          title: string | null
          url: string
        }
        Insert: {
          author?: string | null
          body?: string | null
          canonical_url: string
          content_hash?: string | null
          created_at?: string
          duplicate_of?: string | null
          external_id?: string | null
          fetched_at?: string
          id?: string
          language?: string | null
          last_pipeline_run_id?: string | null
          media?: Json
          metadata?: Json
          published_at?: string | null
          relevance?: Json | null
          relevance_score?: number | null
          simhash?: number | null
          source_id?: string | null
          status?: string
          summary?: string | null
          tags?: string[]
          tenant_id: string
          title?: string | null
          url: string
        }
        Update: {
          author?: string | null
          body?: string | null
          canonical_url?: string
          content_hash?: string | null
          created_at?: string
          duplicate_of?: string | null
          external_id?: string | null
          fetched_at?: string
          id?: string
          language?: string | null
          last_pipeline_run_id?: string | null
          media?: Json
          metadata?: Json
          published_at?: string | null
          relevance?: Json | null
          relevance_score?: number | null
          simhash?: number | null
          source_id?: string | null
          status?: string
          summary?: string | null
          tags?: string[]
          tenant_id?: string
          title?: string | null
          url?: string
        }
        Relationships: [
          {
            foreignKeyName: "articles_duplicate_of_fkey"
            columns: ["duplicate_of"]
            isOneToOne: false
            referencedRelation: "articles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "articles_source_id_fkey"
            columns: ["source_id"]
            isOneToOne: false
            referencedRelation: "sources"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "articles_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      brand_profiles: {
        Row: {
          audience_description: string | null
          company_description: string | null
          criteria_weights: Json
          files: Json
          filter_criteria: string | null
          id: string
          locales: string[]
          score_threshold: number
          tenant_id: string
          updated_at: string
          voice_config: Json
          voice_examples: Json
        }
        Insert: {
          audience_description?: string | null
          company_description?: string | null
          criteria_weights?: Json
          files?: Json
          filter_criteria?: string | null
          id?: string
          locales?: string[]
          score_threshold?: number
          tenant_id: string
          updated_at?: string
          voice_config?: Json
          voice_examples?: Json
        }
        Update: {
          audience_description?: string | null
          company_description?: string | null
          criteria_weights?: Json
          files?: Json
          filter_criteria?: string | null
          id?: string
          locales?: string[]
          score_threshold?: number
          tenant_id?: string
          updated_at?: string
          voice_config?: Json
          voice_examples?: Json
        }
        Relationships: [
          {
            foreignKeyName: "brand_profiles_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: true
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      feedback: {
        Row: {
          comment: string | null
          created_at: string
          edited_diff: Json | null
          id: string
          rating: number | null
          target_id: string
          target_type: string
          tenant_id: string
          user_id: string | null
        }
        Insert: {
          comment?: string | null
          created_at?: string
          edited_diff?: Json | null
          id?: string
          rating?: number | null
          target_id: string
          target_type: string
          tenant_id: string
          user_id?: string | null
        }
        Update: {
          comment?: string | null
          created_at?: string
          edited_diff?: Json | null
          id?: string
          rating?: number | null
          target_id?: string
          target_type?: string
          tenant_id?: string
          user_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "feedback_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "feedback_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      pipeline_runs: {
        Row: {
          drafted: number
          duplicated: number
          extracted: number
          failed: number
          fetched: number
          filtered_out: number
          finished_at: string | null
          id: string
          mode: string
          new: number
          run_date: string
          scored: number
          started_at: string
          stats: Json
          status: string
          tenant_id: string
        }
        Insert: {
          drafted?: number
          duplicated?: number
          extracted?: number
          failed?: number
          fetched?: number
          filtered_out?: number
          finished_at?: string | null
          id?: string
          mode?: string
          new?: number
          run_date: string
          scored?: number
          started_at?: string
          stats?: Json
          status?: string
          tenant_id: string
        }
        Update: {
          drafted?: number
          duplicated?: number
          extracted?: number
          failed?: number
          fetched?: number
          filtered_out?: number
          finished_at?: string | null
          id?: string
          mode?: string
          new?: number
          run_date?: string
          scored?: number
          started_at?: string
          stats?: Json
          status?: string
          tenant_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "pipeline_runs_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      platform_admins: {
        Row: {
          created_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "platform_admins_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: true
            referencedRelation: "users"
            referencedColumns: ["id"]
          },
        ]
      }
      posts: {
        Row: {
          ai_cost_usd: number | null
          ai_model: string | null
          article_id: string | null
          body_markdown: string | null
          created_at: string
          faq: Json
          id: string
          json_ld: Json | null
          language: string | null
          seo: Json
          status: string
          suggested_titles: string[]
          tenant_id: string
          title: string | null
          updated_at: string
        }
        Insert: {
          ai_cost_usd?: number | null
          ai_model?: string | null
          article_id?: string | null
          body_markdown?: string | null
          created_at?: string
          faq?: Json
          id?: string
          json_ld?: Json | null
          language?: string | null
          seo?: Json
          status?: string
          suggested_titles?: string[]
          tenant_id: string
          title?: string | null
          updated_at?: string
        }
        Update: {
          ai_cost_usd?: number | null
          ai_model?: string | null
          article_id?: string | null
          body_markdown?: string | null
          created_at?: string
          faq?: Json
          id?: string
          json_ld?: Json | null
          language?: string | null
          seo?: Json
          status?: string
          suggested_titles?: string[]
          tenant_id?: string
          title?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "posts_article_id_fkey"
            columns: ["article_id"]
            isOneToOne: false
            referencedRelation: "articles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "posts_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      source_secrets: {
        Row: {
          secrets: Json
          source_id: string
          tenant_id: string
          updated_at: string
        }
        Insert: {
          secrets?: Json
          source_id: string
          tenant_id: string
          updated_at?: string
        }
        Update: {
          secrets?: Json
          source_id?: string
          tenant_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "source_secrets_source_id_fkey"
            columns: ["source_id"]
            isOneToOne: true
            referencedRelation: "sources"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "source_secrets_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      sources: {
        Row: {
          category: string | null
          config: Json
          created_at: string
          enabled: boolean
          id: string
          last_error: string | null
          last_error_at: string | null
          last_run_at: string | null
          last_status: string | null
          next_run_at: string | null
          priority: number
          state: Json
          tenant_id: string
          title: string | null
          type: string
          url: string
        }
        Insert: {
          category?: string | null
          config?: Json
          created_at?: string
          enabled?: boolean
          id?: string
          last_error?: string | null
          last_error_at?: string | null
          last_run_at?: string | null
          last_status?: string | null
          next_run_at?: string | null
          priority?: number
          state?: Json
          tenant_id: string
          title?: string | null
          type: string
          url: string
        }
        Update: {
          category?: string | null
          config?: Json
          created_at?: string
          enabled?: boolean
          id?: string
          last_error?: string | null
          last_error_at?: string | null
          last_run_at?: string | null
          last_status?: string | null
          next_run_at?: string | null
          priority?: number
          state?: Json
          tenant_id?: string
          title?: string | null
          type?: string
          url?: string
        }
        Relationships: [
          {
            foreignKeyName: "sources_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
      tenants: {
        Row: {
          ai_budget_usd_month: number
          ai_spent_usd_month: number
          created_at: string
          default_locale: string
          id: string
          name: string
          pipeline_hour_local: number
          plan: string
          timezone: string
          upsell_threshold_pct: number
        }
        Insert: {
          ai_budget_usd_month?: number
          ai_spent_usd_month?: number
          created_at?: string
          default_locale?: string
          id?: string
          name: string
          pipeline_hour_local?: number
          plan?: string
          timezone?: string
          upsell_threshold_pct?: number
        }
        Update: {
          ai_budget_usd_month?: number
          ai_spent_usd_month?: number
          created_at?: string
          default_locale?: string
          id?: string
          name?: string
          pipeline_hour_local?: number
          plan?: string
          timezone?: string
          upsell_threshold_pct?: number
        }
        Relationships: []
      }
      users: {
        Row: {
          created_at: string
          email: string
          id: string
          locale: string
          role: string
          tenant_id: string
        }
        Insert: {
          created_at?: string
          email: string
          id: string
          locale?: string
          role?: string
          tenant_id: string
        }
        Update: {
          created_at?: string
          email?: string
          id?: string
          locale?: string
          role?: string
          tenant_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "users_tenant_id_fkey"
            columns: ["tenant_id"]
            isOneToOne: false
            referencedRelation: "tenants"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      admin_tenant_report: {
        Args: { p_since: string }
        Returns: {
          ai_budget_usd_month: number
          created_at: string
          drafts_month: number
          name: string
          plan: string
          spend_month: number
          tenant_id: string
          upsell_threshold_pct: number
          users_count: number
        }[]
      }
      admin_tenant_usage_by_stage: {
        Args: { p_since: string; p_tenant_id: string }
        Returns: {
          calls: number
          cost_usd: number
          stage: string
        }[]
      }
      current_tenant_id: { Args: never; Returns: string }
      tenant_month_spend: { Args: never; Returns: number }
      tenant_month_usage_by_stage: {
        Args: never
        Returns: {
          calls: number
          cost_usd: number
          stage: string
        }[]
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const

