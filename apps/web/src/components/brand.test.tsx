import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Brand } from "./brand";
vi.mock("next/link",()=>({default:({children,...props}:React.AnchorHTMLAttributes<HTMLAnchorElement>)=><a {...props}>{children}</a>}));
describe("Brand",()=>{it("renders the Arabic product name",()=>{render(<Brand locale="ar"/>);expect(screen.getByRole("link")).toHaveTextContent("عالم الإسلام")})});
