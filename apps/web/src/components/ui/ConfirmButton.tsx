"use client";

import { Button, Modal, ModalBody, ModalHeader } from "flowbite-react";
import { useState } from "react";

type ButtonColor = "failure" | "warning" | "gray" | "blue" | "light";

interface ConfirmButtonProps {
  label: string;
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  color?: ButtonColor;
  size?: "xs" | "sm";
  disabled?: boolean;
}

export const ConfirmButton: React.FC<ConfirmButtonProps> = (props) => {
  const [open, setOpen] = useState(false);

  const confirm = (): void => {
    setOpen(false);
    props.onConfirm();
  };

  return (
    <>
      <Button
        color={props.color ?? "light"}
        size={props.size ?? "xs"}
        disabled={props.disabled}
        onClick={() => setOpen(true)}
      >
        {props.label}
      </Button>
      <Modal show={open} size="md" popup onClose={() => setOpen(false)}>
        <ModalHeader />
        <ModalBody>
          <div className="text-center">
            <h3 className="mb-2 text-lg font-medium text-gray-900 dark:text-white">{props.title}</h3>
            <p className="mb-5 text-sm text-gray-500 dark:text-gray-400">{props.message}</p>
            <div className="flex justify-center gap-3">
              <Button color={props.color ?? "failure"} onClick={confirm}>
                {props.confirmLabel}
              </Button>
              <Button color="light" onClick={() => setOpen(false)}>
                {props.cancelLabel}
              </Button>
            </div>
          </div>
        </ModalBody>
      </Modal>
    </>
  );
};
