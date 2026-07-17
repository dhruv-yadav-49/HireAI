from typing import Any


class CampaignPerformanceEngine:
    @classmethod
    def compile_statistics(
        cls,
        sent: int = 100,
        opened: int = 45,
        clicked: int = 18,
        replied: int = 8,
        converted: int = 4,
        bounced: int = 2,
        unsubscribed: int = 1,
        spam_complaints: int = 0,
        revenue: float = 24000.00
    ) -> dict[str, Any]:
        """Compiles standardized performance metrics partitioned into delivery, engagement, and business segments."""
        
        open_rate = opened / sent if sent > 0 else 0.0
        ctr = clicked / sent if sent > 0 else 0.0
        bounce_rate = bounced / sent if sent > 0 else 0.0
        unsub_rate = unsubscribed / sent if sent > 0 else 0.0
        conv_rate = converted / sent if sent > 0 else 0.0

        return {
            "delivery": {
                "sent": sent,
                "bounced": bounced,
                "bounce_rate": round(bounce_rate, 4),
                "spam_complaints": spam_complaints
            },
            "engagement": {
                "opened": opened,
                "open_rate": round(open_rate, 4),
                "clicked": clicked,
                "ctr": round(ctr, 4),
                "unsubscribed": unsubscribed,
                "unsubscribe_rate": round(unsub_rate, 4)
            },
            "business": {
                "replied": replied,
                "converted": converted,
                "conversion_rate": round(conv_rate, 4),
                "revenue_attribution": revenue
            }
        }


class CampaignAnalyticsEngine:
    @classmethod
    def analyze_campaigns(
        cls,
        campaigns_stats: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Compares campaign stats, detects high-performing metrics, and suggests optimization feedback."""
        total_rev = 0.0
        total_sent = 0
        total_clicks = 0

        best_ctr = -1.0
        best_campaign = None

        for stat in campaigns_stats:
            name = stat["name"]
            statistics = stat["statistics"]
            
            delivery = statistics.get("delivery", {})
            engagement = statistics.get("engagement", {})
            business = statistics.get("business", {})

            total_rev += float(business.get("revenue_attribution", 0.0))
            sent_count = int(delivery.get("sent", 0))
            total_sent += sent_count
            
            click_count = int(engagement.get("clicked", 0))
            total_clicks += click_count

            ctr = click_count / sent_count if sent_count > 0 else 0.0
            if ctr > best_ctr:
                best_ctr = ctr
                best_campaign = name

        overall_ctr = total_clicks / total_sent if total_sent > 0 else 0.0

        return {
            "total_revenue_attributed": total_rev,
            "overall_ctr": round(overall_ctr, 4),
            "best_performing_campaign": {
                "name": best_campaign,
                "ctr": round(best_ctr, 4)
            },
            "recommendation_feedback": "Nurturing campaigns targeting high value leads show higher CTR. Propose allocating larger traffic to variant splits."
        }
