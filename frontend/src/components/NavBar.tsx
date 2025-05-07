import { useAuthenticator } from "@aws-amplify/ui-react";
import TopNavigation from "@cloudscape-design/components/top-navigation";
import { useEffect, useState } from "react";
import { fetchUserAttributes } from "aws-amplify/auth";
import { config } from "../lib/config";
// Define the type for user attributes
type UserAttributes = {
  email?: string;
  [key: string]: string | undefined;
};

export default function NavBar() {
  const { user, signOut } = useAuthenticator((context) => [context.user]);

  
  // Update the type to match fetchUserAttributes output
  const [userAttributes, setUserAttributes] = useState<UserAttributes>({});

  // Alternative approach using fetchUserAttributes
  useEffect(() => {
    async function getUserAttributes() {
      try {
        const attributes = await fetchUserAttributes();
        setUserAttributes(attributes);
      } catch (error) {
        console.log('Error fetching user attributes:', error);
      }
    }
    
    if (user) {
      getUserAttributes();
    }
  }, [user]);

  return (
    <TopNavigation
      identity={{
        href: "/",
        title: config.APP_NAME,
      }}
      utilities={[
        {
          type: "menu-dropdown",
          text: userAttributes?.email || "Customer Name",
          description: userAttributes?.email || "email@example.com",
          iconName: "user-profile",
          onItemClick: (item) => {
            if (item.detail.id === 'signout') signOut()
          },
          items: [
            { id: "signout", text: "Sign out" }
          ]
        }
      ]}
    />
  );
}
